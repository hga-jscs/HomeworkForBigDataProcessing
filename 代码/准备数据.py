from 公共设置 import ROOT, save_json, sha256
import urllib.request, zipfile, csv, time, datetime, platform, sys
import openpyxl

def main():
    start = time.perf_counter()
    url = 'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip'
    archive = ROOT / '数据' / '原始交易.zip'
    if not archive.exists():
        print('Downloading UCI dataset...', flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, open(archive.with_suffix('.下载中'), 'wb') as f:
            while block := response.read(1024 * 1024):
                f.write(block)
        archive.with_suffix('.下载中').replace(archive)
    workbook_path = ROOT / '数据' / '原始交易.xlsx'
    if not workbook_path.exists():
        with zipfile.ZipFile(archive) as z:
            names = [n for n in z.namelist() if n.endswith('.xlsx')]
            assert len(names) == 1, names
            with z.open(names[0]) as src, open(workbook_path, 'wb') as dst:
                while block := src.read(1024 * 1024):
                    dst.write(block)
    csv_path = ROOT / '数据' / '原始交易.csv'
    if not csv_path.exists():
        wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
        sheets = {}
        with open(csv_path.with_suffix('.转换中'), 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['invoice','stock','description','quantity','time','price','customer','country','sheet','row_number'])
            for sheet in wb:
                rows = sheet.iter_rows(values_only=True)
                header = next(rows)
                print('Sheet', sheet.title, header, flush=True)
                count = 0
                for row_number, row in enumerate(rows, 2):
                    row = list(row[:8])
                    if isinstance(row[4], datetime.datetime):
                        row[4] = row[4].isoformat(sep=' ')
                    for i in (0, 1, 6):
                        if isinstance(row[i], (int, float)) and row[i] == int(row[i]):
                            row[i] = str(int(row[i]))
                    writer.writerow(row + [sheet.title, row_number])
                    count += 1
                    if count % 100000 == 0:
                        print(sheet.title, count, flush=True)
                sheets[sheet.title] = count
        wb.close()
        csv_path.with_suffix('.转换中').replace(csv_path)
        save_json('数据来源.json', {'url':url, 'dataset_doi':'10.24432/C5CG6D', 'license':'CC BY 4.0', 'download_date':datetime.datetime.now().isoformat(), 'archive_sha256':sha256(archive), 'xlsx_sha256':sha256(workbook_path), 'csv_sha256':sha256(csv_path), 'sheets':sheets, 'download_and_conversion_seconds': time.perf_counter()-start})
    print('Raw input ready', csv_path, flush=True)

if __name__ == '__main__':
    main()
