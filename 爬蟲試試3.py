import os
import time
import getpass
from pathlib import Path
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 路徑設定：以本檔案所在資料夾為基準，換電腦、換帳號都不用改路徑
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "下載的數據"


# ==========================================
# 帳號密碼設定
# 讀取順序：環境變數 → 本機帳密檔 (credentials.txt) → 現場輸入
#
# credentials.txt 格式（存在跟這支程式同一個資料夾）：
#   第一行：帳號
#   第二行：密碼
#
# 這個檔案第一次執行時會自動幫你建立空白範本，
# 填好之後下次執行就不用再手動輸入。
# 【重要】這個檔案不要分享、不要上傳、不要一起寄給別人——
# 只有這支主程式（爬蟲試試3.py）可以放心分享。
# ==========================================
CREDENTIALS_FILE = BASE_DIR / "credentials.txt"


def get_credentials():
    user = os.environ.get("AIRTW_USER")
    pwd = os.environ.get("AIRTW_PASS")
    if user and pwd:
        return user, pwd

    if CREDENTIALS_FILE.exists():
        lines = CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines()
        lines = [line.strip() for line in lines if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
        print(f"⚠️ {CREDENTIALS_FILE.name} 內容不完整（需要兩行：帳號、密碼），改為現場輸入。")
    else:
        CREDENTIALS_FILE.write_text("你的帳號\n你的密碼\n", encoding="utf-8")
        print(f"📝 已在此資料夾建立 {CREDENTIALS_FILE.name}，打開它填入帳號密碼後，下次執行就不用再手動輸入。")

    user = user or input("請輸入登入帳號：").strip()
    pwd = pwd or getpass.getpass("請輸入登入密碼（畫面上不會顯示，屬正常現象）：")
    return user, pwd


def get_target_date():
    """讓使用者決定要查詢的日期，回傳 (網頁輸入格式, 檔名格式)"""
    print("\n=========================================")
    print("📅 歡迎使用 SO2 爬蟲小幫手")
    user_input = input(
        "請輸入想查詢的日期 (可輸入 2026/09/15 或 20260915)。\n"
        "👉 若想直接查詢「前一天」，請【直接按 Enter 鍵】: "
    )

    clean_input = user_input.strip().replace("-", "/")

    if clean_input == "":
        target_date = datetime.today() + timedelta(-1)
    else:
        try:
            if len(clean_input) == 8 and clean_input.isdigit():
                target_date = datetime.strptime(clean_input, "%Y%m%d")
            else:
                target_date = datetime.strptime(clean_input, "%Y/%m/%d")
        except ValueError:
            print("❌ 輸入的格式好像怪怪的喔！程式自動幫你切換為「前一天」。")
            target_date = datetime.today() + timedelta(-1)

    ymd_str = target_date.strftime('%Y/%m/%d')      # 網頁輸入用：2026/09/15
    file_ymd_str = target_date.strftime('%Y%m%d')   # 檔名用：20260915

    print(f"✅ 本次將查詢的日期為：{ymd_str}")
    print("=========================================\n")
    return ymd_str, file_ymd_str


def download_so2_daily_max(ymd_str=None, file_ymd_str=None):
    """
    執行爬蟲，回傳下載後的檔案完整路徑；失敗回傳 None。
    可被其他程式 import 呼叫，也可以直接執行本檔互動輸入日期。
    """
    if ymd_str is None or file_ymd_str is None:
        ymd_str, file_ymd_str = get_target_date()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    user, pwd = get_credentials()

    chrome_options = webdriver.ChromeOptions()
    prefs = {"download.default_directory": str(DATA_DIR)}
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--start-maximized")

    print("啟動瀏覽器中...")
    browser = webdriver.Chrome(options=chrome_options)
    browser.maximize_window()

    wait_long = WebDriverWait(browser, 40)
    wait = WebDriverWait(browser, 15)

    final_file_path = None

    try:
        browser.get('https://airtw.moenv.gov.tw/AirQualityExpert/Login.aspx')

        print("網頁已開啟！正在幫你自動輸入帳號密碼...")
        browser.find_element(By.ID, 'txtUI').clear()
        browser.find_element(By.ID, 'txtUI').send_keys(user)
        browser.find_element(By.ID, 'txtpwd').clear()
        browser.find_element(By.ID, 'txtpwd').send_keys(pwd)

        print("\n=========================================")
        print("👉 請在網頁中「手動輸入驗證碼」，並點擊「登入」！")
        print("⏳ 程式會在這裡等待 (最多 40 秒)，只要你一登入就會瞬間接手...")
        print("=========================================")

        menu_analysis = wait_long.until(EC.element_to_be_clickable((By.LINK_TEXT, "資料展示分析")))
        print('✅ 登入成功！程式接手後續自動化作業...')
        time.sleep(1)

        print("正在前往「每日最大值」報表頁面...")
        menu_analysis.click()
        time.sleep(1.5)

        submenu_daily_max = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "每日最大值")))
        submenu_daily_max.click()
        time.sleep(3)

        print("設定查詢條件中...")
        btn_all_site = wait.until(EC.element_to_be_clickable((By.ID, "quick_allSiteList")))
        browser.execute_script("arguments[0].click();", btn_all_site)
        time.sleep(1)

        date_from = browser.find_element(By.ID, "CPHCont_site_list_txt_Stime")
        browser.execute_script("arguments[0].value = arguments[1];", date_from, ymd_str)

        date_to = browser.find_element(By.ID, "CPHCont_site_list_txt_Etime")
        browser.execute_script("arguments[0].value = arguments[1];", date_to, ymd_str)

        so2_checkbox = browser.find_element(By.ID, "CPHCont_site_list_cbl_type1_2")
        if not so2_checkbox.is_selected():
            browser.execute_script("arguments[0].click();", so2_checkbox)

        print("條件設定完成，準備查詢與下載...")
        btn_query = browser.find_element(By.ID, "CPHCont_btnQuery")
        browser.execute_script("arguments[0].click();", btn_query)

        print("查詢中，等待報表產生...")
        # 【修正】原本用固定 time.sleep(6) 賭網站速度，改成主動等按鈕出現，
        # 網站慢的時候不會抓空、網站快的時候也不會白等。
        btn_download = wait_long.until(
            EC.element_to_be_clickable((By.XPATH, "//*[@value='報表下載' or contains(text(), '報表下載')]"))
        )

        files_before = set(os.listdir(DATA_DIR))
        browser.execute_script("arguments[0].click();", btn_download)
        print("已點擊報表下載，等待檔案下載完成...")

        # 【修正】原本只看第一輪出現的檔案，可能抓到還在下載中的 .crdownload。
        # 改成每一輪都篩掉未完成的暫存檔，抓到「真正下載完成」的檔名才停止。
        new_file = None
        for _ in range(60):
            files_after = set(os.listdir(DATA_DIR))
            added = files_after - files_before
            done_files = [f for f in added if not f.endswith(('.crdownload', '.tmp'))]
            if done_files:
                new_file = done_files[0]
                break
            time.sleep(1)

        if new_file:
            old_file_path = DATA_DIR / new_file
            file_ext = old_file_path.suffix

            new_file_name = f"{file_ymd_str} SO2{file_ext}"
            final_file_path = DATA_DIR / new_file_name

            if final_file_path.exists():
                final_file_path.unlink()

            old_file_path.rename(final_file_path)
            print(f"🎉 成功！檔案已儲存並重新命名為：{new_file_name}")
        else:
            print("❌ 警告：等待 60 秒仍找不到新下載的檔案，請確認網站是否正常。")

    except Exception as e:
        print(f"\n❌ 執行過程中發生錯誤：{e}")

    finally:
        print("3秒後關閉瀏覽器...")
        time.sleep(3)
        browser.quit()

    return str(final_file_path) if final_file_path else None


if __name__ == '__main__':
    download_so2_daily_max()
