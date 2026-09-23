import sys
from pathlib import Path

# 【修正】原本這支檔案把爬蟲和出圖的程式碼整段複製貼上，
# 之後改分級門檻、改欄位，必須兩邊都改，很容易漏掉一邊。
# 改成直接 import 另外兩支檔案的函式，邏輯只維護一份，
# 這支檔案只負責「串起流程」。
#
# 三支檔案請放在同一個資料夾底下執行。
sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib

scraper = importlib.import_module("爬蟲試試3")
report = importlib.import_module("試試可互動的呈現方式3")


def main():
    print("\n" + "=" * 50)
    print("🚀 歡迎使用 SO2 一鍵自動化系統 (爬蟲下載 ➡️ 報表出圖)")
    print("=" * 50)

    ymd_str, file_ymd_str = scraper.get_target_date()

    print(">>> 啟動第一階段：自動化網頁爬蟲 <<<")
    downloaded_file = scraper.download_so2_daily_max(ymd_str, file_ymd_str)

    if not downloaded_file or not Path(downloaded_file).exists():
        print("⚠️ 無法找到爬蟲下載的檔案，已終止出圖作業。請檢查網路或網頁狀態。")
        return

    print("\n>>> 啟動第二階段：資料處理與互動地圖繪製 <<<")
    output_html, output_excel = report.build_report(file_ymd_str, xls_path=downloaded_file)

    if output_html:
        print("\n🎉🎉🎉 全自動化流程執行完畢！ 🎉🎉🎉")
    else:
        print("⚠️ 出圖階段失敗，請檢查上方錯誤訊息。")


if __name__ == '__main__':
    main()
