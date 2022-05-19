import pdfplumber
import glob
import re
import pandas as pd

class transaction:
  def __init__(self, payor, check, trx_date, amount, batch, batch_date, file,
                receipt=None, voucher=None):
    self.payor = payor
    self.check = check
    self.trx_date = trx_date
    self.amount = amount
    self.batch = batch
    self.batch_date = batch_date
    self.file = file
    self.receipt = receipt
    self.voucher = voucher

def get_file_list(contains='', extension='.pdf'):
  return glob.glob('*' + contains + '*' + extension)

def merge_pdf_pages(pdf_pages):
  pages = ''
  for pdf_page in pdf_pages:
    pages = pages + pdf_page.extract_text() + '\n'
  return pages

def remove_headings(pages):
  receipt_heading = 'ST MARK\'S CO 12172 Report of Receipts - Transaction Details'
  voucher_heading = 'ST MARK\'S CO 12172 Report of Vouchers'
  lines_after_heading = 3
  for i, page in enumerate(pages):
    if (page == receipt_heading) or (page == voucher_heading):
      for j in range(lines_after_heading):
        pages.pop(i)
  return pages

def remove_headers(pages):
  page_headers = [ 'Receipt # Member/Payor',
          'Check # Receipt Date Account: Sub Account Event Description Amount']
  for header in page_headers:
    counts = pages.count(header)
    for i in range(counts):
      pages.remove(header)
  return pages

def clean_receipt_pages(pages):
  pages = remove_headings(pages)
  pages = remove_headers(pages)
  return pages

def is_transaction(line):
  pattern_receipt = '\d\d\d\d \d\d-\d\d-\d\d\d\d'
  pattern_voucher = '\d\d\d \d\d-\d\d-\d\d\d\d'
  if (re.match(pattern_receipt, line)) or (re.match(pattern_voucher, line)):
    return True
  else:
    return False

def is_batch_start(line, pattern = '\d\d-\d\d-\d\d\d\d'):
  if ((line.startswith('Batch: ')) and
    (' Date Processed: ' in line) and
    (re.search(pattern, line))):
    return True
  else:
    return False

def is_batch_end(line, pattern = '\w\w\w\w\w \d\d\d'):
  'Batch 445 Total: 400.00',
  if (line.startswith('Batch ')) and (' Total: ' in line) and (re.match(pattern, line)):
    return True
  else:
    return False

def get_last_number(line, char = ' '):
  amount = line[line.rfind(char) + len(char):]
  amount = amount.replace(',', '')
  try:
    amount = float(amount)
  except:
    amount = float(0)
  return round(amount, 2)

def get_batch(line):
  left = 'Batch: '
  right = ' Date'
  return (int(line[line.rfind(left) + len(left):line.rfind(right)]))

def get_batch_date(line):
  left = 'Processed: '
  return line[line.rfind(left) + len(left):]

def get_payor(line, pattern = '\d\d-\d\d-\d\d\d\d '):
  return line[re.search(pattern, line).span()[1]:]

def get_receipt_or_voucher(line):
  right = ' '
  return int(line[:line.find(right)])

def get_check(line):
  exceptions = ['cash', 'square']
  right = ' '
  check_num = line[:line.find(right)]
  try:
    check_num = int(check_num)
  except:
    check_num = str(check_num)
    if check_num not in exceptions:
      check_num = ''
  return check_num

def get_transaction_date(line, pattern = '\d\d-\d\d-\d\d\d\d '):
  left = re.search(pattern, line).span()[0]
  right = re.search(pattern, line).span()[1] - 1
  return line[left:right]

def is_address(line):
  exceptions = ['P.O. Box ', 'PO Box ', ', ID ', ' Northview ', ', TX ',
    ', WA ', ', OR ', ', MT ', ', NV ', ', CA ', ', CT ']
  for exc in exceptions:
    if exc in line:
      return True
  return False

def is_only_number(line):
  line_no_comma = line.replace(',', '')
  # float
  try:
    amount = float(line_no_comma)
    amount_str = str(amount)
    if len(amount_str) == len(line_no_comma):
      return True
    else:
      return False
  # non float
  except:
    return False

def trx_list_to_df(transaction_list):
  data_dict = {'trx_date':[], 'receipt':[], 'voucher':[], 'check':[],
    'batch':[], 'batch_date':[], 'payor':[], 'amount':[], 'file':[],}
  for trx in transaction_list:
    for col, value in vars(trx).items():
      data_dict[col].append(value)
  return pd.DataFrame(data=data_dict)

def get_transactions(pdf_file):
  with pdfplumber.open(pdf_file) as pdf:
    pages = merge_pdf_pages(pdf.pages)
    lines = clean_receipt_pages(pages.split('\n'))
    num_lines = len(lines)
    i = 0
    transaction_list = []
    while i < num_lines:
      # check for batch
      if is_batch_start(lines[i]):
        batch = get_batch(lines[i])
        batch_date = get_batch_date(lines[i])
      # main if/else condition
      if is_transaction(lines[i]):
        payor = get_payor(lines[i])
        receipt_or_voucher = get_receipt_or_voucher(lines[i])
        check = get_check(lines[i+1])
        trx_date = get_transaction_date(lines[i])
        # move to next line
        i += 1
        # get amounts from transaction breakdown
        total_amount = []
        # make sure not new transaction nor batch end
        while (not is_transaction(lines[i])) and (not is_batch_end(lines[i])):
          # make sure not address nor subtotal line
          if (not is_address(lines[i])) and (not is_only_number(lines[i])):
            total_amount.append(get_last_number(lines[i]))
          i += 1
        # found transaction or batch end
        amount = sum(total_amount)
        if 'Receipt' in pdf_file:
          transaction_list.append(transaction(payor, check, trx_date,
            amount, batch, batch_date, pdf_file, receipt=receipt_or_voucher))
        else:
          transaction_list.append(transaction(payor, check, trx_date,
            -amount, batch, batch_date, pdf_file, voucher=receipt_or_voucher))
      # non transaction
      else:
        i += 1
  return transaction_list

def add_month(df):
  month_dict = {'01': 'jan', '02': 'feb', '03': 'march', '04': 'april',
    '05': 'may', '06': 'june', '07': 'july', '08': 'aug', '09': 'sept',
    '10': 'oct', '11': 'nov', '12': 'dec'}
  df['month'] = df['trx_date'].apply(lambda x: x[:x.find('-')])
  df['month'] = df['month'].replace(month_dict)
  return df

def main():
  pdf_list = get_file_list(contains='*')
  df_list = []
  for pdf in pdf_list:
    print(pdf)
    trx_list = get_transactions(pdf)
    df_list.append(trx_list_to_df(trx_list))
    # file_name = pdf[:-len('.pdf')]
    # new_name = file_name + '.csv'
    # df.to_csv(new_name, index=False)
  df = pd.concat(df_list)
  df = add_month(df)
  df.to_csv('processed.csv', index=False)
  print('done')

if __name__ == '__main__':
  main()
