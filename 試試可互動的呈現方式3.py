import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import folium

# ==========================================
# 路徑設定：以本檔案所在資料夾為基準
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "出圖"
DATA_DIR = BASE_DIR / "下載的數據"

# 備援路徑：如果 .py 檔跟資料檔不在同一個資料夾，會再檢查這裡
# （對應你原本習慣放檔案的固定位置，找不到就跳過，不會報錯）
LEGACY_BASE_DIR = Path(r"C:\Users\9822\Documents\try SO2")

# ==========================================
# 濃度分級設定（地圖顏色 / Excel 等級欄 共用同一份，不會再兜不起來）
# 門檻與名稱如需依實際 AQI 對照表調整，改這裡就好
# ==========================================
LEVELS = [
    (6.5, "極佳", "#00E800"),
    (13.0, "良好", "#FFFF00"),
    (65.0, "普通", "#FF7E00"),
    (float("inf"), "不良", "#FF0000"),
]

# 【修正】原本「異常濃度測站」門檻是 6.5，但地圖圖例把 6.5-12.9 歸類成「良好」，
# 兩邊標準對不上，容易誤導看報表的人。
# 這裡改成：Excel 每一列都附上跟地圖一致的「等級」欄位，
# 「異常」分頁改抓等級為「普通」以上（對應地圖橘色/紅色點），意義更一致。
# 如果你有既定的 6.5 判定依據，把下面這個常數改回 6.5 即可，邏輯不受影響。
FLAG_THRESHOLD = 13.0


def get_level(val):
    if pd.isna(val):
        return "資料缺失", "#999999"
    for upper, name, color in LEVELS:
        if val < upper:
            return name, color
    return LEVELS[-1][1], LEVELS[-1][2]


def build_report(file_ymd_str, xls_path=None):
    """
    讀取指定日期的下載檔，輸出互動地圖 HTML 與 Excel。
    回傳 (output_html, output_excel)；找不到來源檔回傳 (None, None)。
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_candidates = [
        BASE_DIR / "空氣品質監測站基本資料.csv",
        DATA_DIR / "空氣品質監測站基本資料.csv",
        LEGACY_BASE_DIR / "空氣品質監測站基本資料.csv",
        LEGACY_BASE_DIR / "下載的數據" / "空氣品質監測站基本資料.csv",
    ]
    csv_path = next((p for p in csv_candidates if p.exists()), None)
    if csv_path is None:
        print("❌ 找不到【空氣品質監測站基本資料.csv】，已檢查以下位置：")
        for p in csv_candidates:
            print(f"   - {p}")
        print("請確認檔案實際放在哪裡，或直接把它複製到跟這三支程式相同的資料夾。")
        return None, None

    if xls_path is None:
        xls_filename = f"{file_ymd_str} SO2.xls"
        xls_candidates = [
            DATA_DIR / xls_filename,
            BASE_DIR / xls_filename,
            LEGACY_BASE_DIR / "下載的數據" / xls_filename,
            LEGACY_BASE_DIR / xls_filename,
        ]
        xls_path = next((p for p in xls_candidates if p.exists()), xls_candidates[0])
    else:
        xls_path = Path(xls_path)

    if not xls_path.exists():
        print(f"❌ 找不到檔案：{xls_path.name}")
        return None, None

    output_html = OUT_DIR / f"SO2_Interactive_Dashboard_{file_ymd_str}.html"
    output_excel = OUT_DIR / f"SO2_Data_{file_ymd_str}.xlsx"

    print("📊 正在讀取並合併測站資料...")
    df_csv = pd.read_csv(csv_path)
    try:
        df_xls = pd.read_html(xls_path)[0]
    except Exception:
        df_xls = pd.read_excel(xls_path)

    # 【修正】原本用 inner join + dropna，只要測站改名/新設站/CSV沒更新，
    # 該站會無聲無息從地圖和 Excel 消失，完全不會被發現。
    # 改成 left join，並且明確列出被漏掉、無資料的測站，讓問題看得見。
    df = pd.merge(df_xls, df_csv, left_on='測站', right_on='sitename', how='left')

    no_coord = df[df['twd97lat'].isna()]['測站'].tolist()
    if no_coord:
        print(f"⚠️ 下列 {len(no_coord)} 個測站在基本資料 CSV 找不到座標，將不會畫在地圖上：{no_coord}")

    no_value = df[df['最大值'].isna()]['測站'].tolist()
    if no_value:
        print(f"⚠️ 下列 {len(no_value)} 個測站當日無有效值：{no_value}")

    df = df.sort_values(by='最大值', ascending=True, na_position='first')
    date_str = df['日期'].dropna().iloc[0] if df['日期'].notna().any() else file_ymd_str

    # --- 準備 Excel 報表 ---
    # 【修正】經緯度原本存成單一字串，無法排序也無法在 Excel 裡做地圖/計算。
    # 拆成兩個數值欄，另外保留一欄組合字串給需要複製貼上的情況用。
    df['等級'] = df['最大值'].apply(lambda v: get_level(v)[0])
    df['測站緯度'] = df['twd97lat']
    df['測站經度'] = df['twd97lon']
    df['測站經緯度'] = df.apply(
        lambda row: f"{row['twd97lat']:.4f}, {row['twd97lon']:.4f}" if pd.notna(row['twd97lat']) else "",
        axis=1
    )

    df_excel = df[['county', '測站', '測站緯度', '測站經度', '測站經緯度', '最大值', '等級', '日期']].copy()
    df_excel.columns = ['縣市名稱', '測站地點', '緯度', '經度', '測站經緯度', 'SO2最大值', '等級', '日期']
    df_excel['日期'] = df_excel['日期'].fillna(file_ymd_str)

    df_abnormal = df_excel[df_excel['SO2最大值'] >= FLAG_THRESHOLD]

    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        df_excel.to_excel(writer, sheet_name='所有測站資料', index=False)
        df_abnormal.to_excel(writer, sheet_name='異常濃度測站', index=False)

        # 【新增】欄寬與凍結首列，原本欄位標題會被截斷、捲動時看不到標題
        for sheet_name, sheet_df in [('所有測站資料', df_excel), ('異常濃度測站', df_abnormal)]:
            ws = writer.sheets[sheet_name]
            widths = [12, 14, 10, 10, 16, 12, 8, 12]
            for col_idx, width in enumerate(widths, start=1):
                ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width
            ws.freeze_panes = 'A2'

    print(f"✅ Excel 報表已成功儲存至:\n   {output_excel}")

    print("\n" + "=" * 50)
    print(f" ⚠️ 異常濃度測站名單 (SO2 >= {FLAG_THRESHOLD} ppb) ⚠️")
    print("=" * 50)
    if not df_abnormal.empty:
        print(df_abnormal.to_string(index=False))
    else:
        print(f"🎉 今日所有測站 SO2 濃度皆 < {FLAG_THRESHOLD} ppb，無異常！")
    print("=" * 50 + "\n")

    # --- 繪製互動式地圖 ---
    print("🎨 正在生成互動式地圖網頁...")
    google_map_url = 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}'
    m = folium.Map(
        location=[23.7, 120.9],
        zoom_start=8,
        tiles=google_map_url,
        attr='Google Maps'
    )

    for _, row in df.iterrows():
        val = row['最大值']
        station_name = row['測站']
        level_name, color_hex = get_level(val)

        if pd.isna(row['twd97lat']) or pd.isna(row['twd97lon']):
            continue  # 沒有座標的站沒辦法畫在地圖上，但已在 Excel 保留紀錄

        value_text = "無有效值" if pd.isna(val) else f"{val} ppb"
        # 【新增】半徑隨數值放大，高濃度測站在圖上會自己跳出來，不會被埋在一堆綠點裡
        radius = 6 if pd.isna(val) else min(6 + val / 5, 16)

        tooltip_html = f"""
        <div style="font-family: 'Microsoft JhengHei', sans-serif; font-size: 14px;">
            <b>測站：{station_name}</b><br>
            SO2 最大值：<span style="font-size: 16px; color: {color_hex}; text-shadow: 1px 1px 1px rgba(0,0,0,0.5);"><b>{value_text}</b></span><br>
            等級：{level_name}
        </div>
        """

        folium.CircleMarker(
            location=[row['twd97lat'], row['twd97lon']],
            radius=radius,
            color='black',
            weight=1,
            fill=True,
            fill_color=color_hex,
            fill_opacity=0.85,
            tooltip=tooltip_html
        ).add_to(m)

    generated_at = datetime.now().strftime('%Y/%m/%d %H:%M')
    # 【新增】圖例補上資料來源、產製時間、以及「日最大小時值」的說明，避免被誤讀成日均值
    legend_html = f'''
         <div style="position: fixed;
                     bottom: 30px; left: 30px; width: 240px;
                     border:2px solid grey; z-index:9999; font-size:13px;
                     background-color:white; padding: 10px; font-family: 'Microsoft JhengHei', sans-serif; border-radius: 8px;">
         <b>SO2 濃度指標（日最大小時值）</b><br>
         資料日期：{date_str}<br><br>
         <i style="background:#FF0000; width: 16px; height: 16px; float: left; margin-right: 8px; border: 1px solid black;"></i> ≥ 65.0 ppb (不良)<br>
         <i style="background:#FF7E00; width: 16px; height: 16px; float: left; margin-right: 8px; border: 1px solid black;"></i> 13.0 - 64.9 ppb (普通)<br>
         <i style="background:#FFFF00; width: 16px; height: 16px; float: left; margin-right: 8px; border: 1px solid black;"></i> 6.5 - 12.9 ppb (良好)<br>
         <i style="background:#00E800; width: 16px; height: 16px; float: left; margin-right: 8px; border: 1px solid black;"></i> &lt; 6.5 ppb (極佳)<br>
         <i style="background:#999999; width: 16px; height: 16px; float: left; margin-right: 8px; border: 1px solid black;"></i> 無有效值<br>
         <hr style="margin:6px 0;">
         資料來源：環境部空氣品質監測網<br>
         產製時間：{generated_at}
         </div>
         '''
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(str(output_html))
    print(f"✅ 互動式儀表板地圖已成功儲存至:\n   {output_html}")

    return str(output_html), str(output_excel)


if __name__ == '__main__':
    target_date = input("📝 請輸入您想要出圖的日期 (例如 20260910): ").strip()
    result = build_report(target_date)
    if result == (None, None):
        sys.exit(1)