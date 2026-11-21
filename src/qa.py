import pandas as pd
import numpy as np
from pathlib import Path
import html
import logging
import shutil
from itertools import combinations
# Tính từ vị trí qa.py, không phụ thuộc thư mục đang mở terminal.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
ROOT = Path(__file__).resolve().parent.parent
# Mô tả quy tắc dùng để tổng hợp báo cáo QA.
# Các điều kiện kiểm tra thực tế được viết trong các hàm check_*.
TAG = r"<[a-zA-Z/][^>]*>"
DEFAULT_QA_CONFIG = {
    "price_max": 2000.0,
    "min_nights_cap": 365,
    "iqr_multiplier": 1.5,
    "room_types": ["Entire home/apt", "Private room"],
    "valid_areas": ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08"],
}

RULES = {
    # Quy tắc dùng chung cho nhiều bảng
    "missing_listing_id": {
        "table": "listings,reviews,calendar",
        "condition": "Mã listing bị null, rỗng hoặc chỉ chứa khoảng trắng",
        "reason": "Không xác định được listing để liên kết dữ liệu",
        "action": "Gắn cờ nghiêm trọng, giữ dòng để kiểm tra",
    },
    "date_missing": {
        "table": "reviews,calendar",
        "condition": "date gốc bị null, rỗng hoặc chỉ chứa khoảng trắng",
        "reason": "Không có ngày để phân tích theo thời gian",
        "action": "Gắn cờ, giữ ngày gốc và không tự điền",
    },
    "wrong_date_type": {
        "table": "reviews,calendar",
        "condition": "Ngày gốc không thiếu nhưng không chuyển được sang datetime",
        "reason": "Không xác định được ngày để phân tích theo thời gian",
        "action": "Giữ ngày gốc, tạo cột ngày đã chuyển kiểu và gắn cờ",
    },
    "listing_not_found": {
        "table": "reviews,calendar",
        "condition": (
            "listing_id không thiếu nhưng không tồn tại "
            "trong bảng listings của nhóm cùng mốc"
        ),
        "reason": "Bản ghi không liên kết được với listings trong phạm vi nhóm",
        "action": "Gắn cờ, giữ dòng để kiểm tra",
    },
    # Listings
    "duplicate_listing_full_row": {
        "table": "listings",
        "condition": "Các cột của listings đã chuẩn bị giống nhau hoàn toàn trong cùng mốc",
        "reason": "Bản ghi listing có thể được lưu lặp",
        "action": "Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa",
    },
    "duplicate_listing": {
        "table": "listings",
        "condition": "listing_id không thiếu xuất hiện nhiều lần trong cùng mốc",
        "reason": "Một listing chỉ nên có một bản ghi trong mỗi mốc",
        "action": "Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa",
    },
    "missing_price": {
        "table": "listings",
        "condition": "Giá gốc bị thiếu",
        "reason": "Không đủ dữ liệu để phân tích giá",
        "action": "Gắn cờ, giữ dòng và không tự điền",
    },
    "wrong_price_type": {
        "table": "listings",
        "condition": (
            "Giá gốc không thiếu nhưng sau chuẩn hóa ký hiệu tiền tệ "
            "và dấu phân cách vẫn không chuyển được sang numeric"
        ),
        "reason": "Giá sai định dạng, không dùng được để tính toán",
        "action": "Giữ giá gốc, tạo cột giá numeric và gắn cờ lỗi chuyển đổi",
    },
    "invalid_price": {
        "table": "listings",
        "condition": "Giá <= 0",
        "reason": "Giá phòng không hợp lý",
        "action": "Gắn cờ, giữ dữ liệu gốc",
    },
    "price_outlier": {
        "table": "listings",
        "condition": (
            "Giá dương vượt trần cấu hình (qa.price_max) hoặc nằm ngoài "
            "[Q1 - iqr_multiplier*IQR, Q3 + iqr_multiplier*IQR] tính riêng theo từng room_type "
            "(fallback toàn mốc nếu thiếu room_type)"
        ),
        "reason": "Giá khác biệt lớn so với cùng loại phòng hoặc vượt ngưỡng trần cấu hình, cần kiểm tra thêm",
        "action": "Gắn cờ, giữ dữ liệu gốc",
    },
    "missing_minimum_nights": {
        "table": "listings",
        "condition": "minimum_nights bị null hoặc không chuyển được sang số",
        "reason": "Không đủ dữ liệu để kiểm tra quy định số đêm tối thiểu",
        "action": "Gắn cờ riêng tách khỏi cờ ngoài miền, giữ dữ liệu gốc",
    },
    "invalid_minimum_nights": {
        "table": "listings",
        "condition": "minimum_nights sau chuyển kiểu thành công <= 0 hoặc > qa.min_nights_cap",
        "reason": "Số đêm tối thiểu ngoài miền hợp lý",
        "action": "Gắn cờ, giữ dữ liệu gốc",
    },
    "invalid_maximum_nights": {
        "table": "listings",
        "condition": "maximum_nights sau chuyển kiểu thành công <= 0",
        "reason": "Số đêm tối đa không hợp lý",
        "action": "Gắn cờ, giữ dữ liệu gốc",
    },
    "min_greater_max": {
        "table": "listings",
        "condition": (
            "minimum_nights và maximum_nights đều chuyển kiểu thành công, "
            "nhưng minimum_nights > maximum_nights"
        ),
        "reason": "Số đêm tối thiểu lớn hơn số đêm tối đa",
        "action": "Gắn cờ, giữ dữ liệu gốc",
    },
    "invalid_availability_365": {
        "table": "listings",
        "condition": "availability_365 sau chuyển kiểu thành công nằm ngoài [0, 365]",
        "reason": "Số ngày còn trống vượt phạm vi 365 ngày hoặc bị âm",
        "action": "Gắn cờ, giữ dữ liệu gốc",
    },
    "category_mismatch": {
        "table": "listings",
        "condition": (
            "room_type không thuộc danh sách qa.room_types hoặc "
            "analysis_area không thuộc qa.valid_areas trong cấu hình; bao gồm giá trị thiếu"
        ),
        "reason": "Giá trị ngoài danh mục hoặc phạm vi phân tích đã quy định",
        "action": "Gắn cờ theo từng cột, giữ giá trị gốc",
    },
    "missing_rating": {
        "table": "listings",
        "condition": "review_scores_rating bị thiếu (thường do chỗ ở chưa có đánh giá)",
        "reason": "Tách riêng giá trị thiếu khỏi lỗi ngoài miền; không tự điền 0",
        "action": "Gắn cờ, giữ NA",
    },
    "invalid_rating": {
        "table": "listings",
        "condition": "review_scores_rating không thiếu nhưng nằm ngoài thang [0, 5]",
        "reason": "Điểm đánh giá nằm ngoài miền giá trị cho phép [0, 5]",
        "action": "Gắn cờ ngoài miền, giữ giá trị gốc để kiểm tra",
    },
    "rows_with_any_flag": {
        "table": "listings,reviews,calendar",
        "condition": "Bản ghi có ít nhất một cờ QA được bật (any(axis=1))",
        "reason": "Phân biệt số hàng cần kiểm tra với tổng số lượt gắn cờ (một hàng có thể mang nhiều cờ)",
        "action": "Ghi nhận tổng số hàng cần xem trong qa_report.csv",
    },
    "room_change": {
        "table": "listings",
        "condition": "Cùng listing_id xuất hiện ở hai mốc nhưng room_type khác nhau",
        "reason": "Theo dõi thay đổi loại phòng giữa các mốc; thay đổi chưa mặc định là lỗi",
        "action": "Chỉ ghi nhận thay đổi giữa các cặp mốc vào qa_report.csv, giữ dòng",
    },
    # Reviews
    "missing_review_id": {
        "table": "reviews",
        "condition": "review_id bị null, rỗng hoặc chỉ chứa khoảng trắng",
        "reason": "Không xác định được review để kiểm tra khóa và đối chiếu giữa các mốc",
        "action": "Gắn cờ nghiêm trọng, giữ dòng để kiểm tra",
    },
    "duplicate_review_full_row": {
        "table": "reviews",
        "condition": "Các cột dữ liệu review gốc giống nhau hoàn toàn trong cùng mốc",
        "reason": "Bản ghi review có thể đã được lưu lặp",
        "action": "Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa",
    },
    "duplicate_review_id": {
        "table": "reviews",
        "condition": "review_id không thiếu xuất hiện nhiều lần trong cùng mốc",
        "reason": "Một review chỉ nên có một bản ghi trong mỗi mốc",
        "action": "Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa",
    },
    "review_after_scrape": {
        "table": "reviews",
        "condition": (
            "Ngày review và last_scraped đều chuyển kiểu thành công, "
            "nhưng ngày review sau ngày last_scraped của listing cùng mốc"
        ),
        "reason": "Review có ngày sau thời điểm thu thập dữ liệu của listing",
        "action": "Gắn cờ, giữ dòng để kiểm tra; không tự sửa ngày",
    },
    "comment_markup": {
        "table": "reviews",
        "condition": "comments gốc chứa thẻ HTML như <br>, <br/> hoặc <p>",
        "reason": "Thẻ HTML gây nhiễu khi phân tích nội dung bình luận",
        "action": (
            "Gắn cờ, giữ comments gốc; tạo comment_clean bằng cách giải mã "
            "HTML, thay thẻ xuống dòng bằng khoảng trắng, bỏ thẻ và gộp khoảng trắng"
        ),
    },
    "comment_empty": {
        "table": "reviews",
        "condition": "Bình luận sau làm sạch HTML và khoảng trắng không còn nội dung, kể cả comments gốc bị thiếu",
        "reason": "Không có nội dung bình luận để phân tích",
        "action": "Gắn cờ, giữ dòng nhưng không dùng để phân tích nội dung hoặc chọn mẫu LLM",
    },
    "review_id_repeated": {
        "table": "reviews",
        "condition": "review_id không thiếu ở mốc thứ nhất xuất hiện ở mốc thứ hai; đếm mỗi ID một lần",
        "reason": "Đo mức giao nhau của reviews giữa hai bản chụp; xuất hiện lại chưa mặc định là lỗi",
        "action": "Chỉ ghi nhận, giữ dòng và không tự loại review xuất hiện lại",
    },
    "date_changed": {
        "table": "reviews",
        "condition": "Cùng review_id không thiếu, duy nhất trong mỗi mốc, có ngày hợp lệ ở cả hai mốc nhưng khác ngày sau chuẩn hóa",
        "reason": "Ngày của cùng một review thay đổi, cần kiểm tra nguồn dữ liệu",
        "action": "Gắn cờ cặp thay đổi, giữ dòng; bỏ cặp có ngày thiếu hoặc sai kiểu",
    },
    "listing_changed": {
        "table": "reviews",
        "condition": "Cùng review_id không thiếu, duy nhất trong mỗi mốc, có listing_id không thiếu ở cả hai mốc nhưng khác nhau",
        "reason": "Cùng review được liên kết với listing khác nhau giữa các mốc",
        "action": "Gắn cờ cặp thay đổi, giữ dòng; bỏ cặp thiếu listing_id",
    },
    "comments_changed": {
        "table": "reviews",
        "condition": "Cùng review_id không thiếu, duy nhất trong mỗi mốc, có comments gốc không thiếu ở cả hai mốc nhưng nội dung khác nhau",
        "reason": "Theo dõi nội dung review thay đổi giữa các bản chụp",
        "action": "Gắn cờ khi same_comments=False, giữ dòng; bỏ cặp thiếu comments, không chuẩn hóa nội dung khi so sánh",
    },
    # Calendar
    "duplicate_calendar_full_row": {
        "table": "calendar",
        "condition": "Các cột của calendar đã chuẩn bị giống nhau hoàn toàn trong cùng mốc",
        "reason": "Bản ghi calendar có thể được lưu lặp",
        "action": "Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa",
    },
    "duplicate_calendar": {
        "table": "calendar",
        "condition": (
            "Cùng cặp (listing_id, date) hợp lệ xuất hiện nhiều lần "
            "trong cùng mốc"
        ),
        "reason": "Một listing tại một ngày chỉ nên có một bản ghi trong mỗi mốc",
        "action": "Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa",
    },
    "missing_available": {
        "table": "calendar",
        "condition": "available bị null, rỗng hoặc chỉ chứa khoảng trắng",
        "reason": "Không xác định được trạng thái còn trống của ngày",
        "action": "Gắn cờ, giữ dòng và không tự điền trạng thái",
    },
    "invalid_available": {
        "table": "calendar",
        "condition": (
            "available sau chuẩn hóa không thuộc t/f/true/false, "
            "bao gồm cả giá trị thiếu và rỗng"
        ),
        "reason": "Trạng thái phòng không thuộc danh mục được chấp nhận",
        "action": "Gắn cờ, giữ giá trị gốc",
    },
    "calendar_available_conflict": {
        "table": "calendar",
        "condition": "Trong cùng mốc, cùng listing_id và ngày hợp lệ có cả trạng thái trống và không trống sau quy đổi t/true, f/false",
        "reason": "Các bản ghi của cùng một ngày có trạng thái mâu thuẫn",
        "action": "Gắn cờ nhóm mâu thuẫn, không dùng ngày đó để tính tỷ lệ available",
    },
}


# ============================================================================
# 1. HÀM DÙNG CHUNG CHO NHIỀU BẢNG
# ============================================================================

def validate_schema(df, required_columns, table_name):
    """Kiểm tra cấu trúc cột bắt buộc trước khi chạy QA (theo Bài 10 §4).

    Thiếu cột bắt buộc thì dừng bằng ValueError; không bỏ qua phép kiểm rồi báo 0 lỗi.
    """
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Bảng {table_name} thiếu cột bắt buộc: {sorted(missing)}")


def missing_listing_id(df):
    """Gắn cờ mã listing bị null, rỗng hoặc chỉ có khoảng trắng."""
    listing_id = df["listing_id"].astype("string")
    missing = listing_id.isna() | listing_id.str.strip().eq("").fillna(False)
    return pd.DataFrame({
        "missing_listing_id" : missing
    })


def check_missing(df):
    """
    Tổng hợp số lượng và tỷ lệ giá trị thiếu theo từng cột của df.

    Trả về DataFrame có index là tên cột, gồm missing_count và
    'missing percent' (đơn vị %). Chỉ tính giá trị thiếu theo isna(),
    không tính chuỗi rỗng hoặc chuỗi chỉ chứa khoảng trắng.
    """
    missing = df.isna().sum()
    missing_pct = df.isna().mean() * 100
    return pd.DataFrame({
        "missing_count" : missing,
        "missing percent": missing_pct
    })


def check_date(df):
    """Chuyển cột date sang datetime và phân loại tình trạng ngày.

    Nhận reviews hoặc calendar có cột date. Trả về date_parsed,
    date_missing, wrong_date_type và date_valid cùng index với df.
    Ngày không chuyển được trở thành NaT; lỗi chuyển kiểu chỉ gắn
    cho giá trị gốc không thiếu. Chưa kiểm tra ngày với mốc thu thập.
    """
    date_raw = df["date"].astype("string").str.strip()
    date_parsed = pd.to_datetime(date_raw, errors="coerce")
    date_missing = date_raw.isna() | date_raw.eq("").fillna(False)
    date_parse_error = ~date_missing & date_parsed.isna()
    date_valid = date_parsed.notna()
    return pd.DataFrame({
        "date_parsed": date_parsed,
        "date_missing" : date_missing,
        "wrong_date_type" : date_parse_error,
        "date_valid" : date_valid
    })


def check_listing_match(reviews_df, listings_df):
    """Kiểm tra mã listing của reviews hoặc calendar có trong listings.

    Hai đầu vào cần có listing_id và thuộc cùng mốc dữ liệu.
    Trả về DataFrame cùng index với bảng thứ nhất, có listing_match
    bằng True khi mã xuất hiện trong listings_df; không loại dòng.
    """
    listing_match = reviews_df["listing_id"].isin(listings_df['listing_id'])
    return pd.DataFrame({
        "listing_match" : listing_match,
        "listing_not_found": (
            ~missing_listing_id(reviews_df)["missing_listing_id"]
            & ~listing_match
        ),
    })



# ============================================================================
# 2. LISTINGS: CHUẨN BỊ, KIỂM TRA, SO SÁNH VÀ XỬ LÝ
# ============================================================================

def prepare_listings(raw_listings, phan_cong, snapshot_date):
    """Chuẩn bị listings của nhóm cho một mốc dữ liệu.

    Nhận listings gốc có cột id và bảng phân công có listing_id,
    analysis_area. Lọc id theo phân công, ghép khu vực phân tích có
    validate='many_to_one' để chống nhân bản dòng, trả về DataFrame
    có thêm listing_id, analysis_area và snapshot_date.
    """
    bang_area = phan_cong[["listing_id", "analysis_area"]].dropna(subset=["listing_id"]).drop_duplicates("listing_id")
    mask = raw_listings["id"].isin(bang_area["listing_id"])
    raw_listings = raw_listings[mask]
    bang_moi = raw_listings.merge(
        bang_area,
        left_on="id",
        right_on="listing_id",
        how="left",
        validate="many_to_one",
    )
    bang_moi["snapshot_date"] = snapshot_date
    return bang_moi


def check_duplicates(df):
    """
    Đánh dấu dòng trùng hoàn toàn và trùng listing_id trong df.

    Đầu vào là listings của một mốc. Trả về hai cột boolean
    duplicate_full_row và duplicate_listing_id, cùng index với df.
    True đánh dấu tất cả dòng thuộc nhóm trùng; không xóa dòng.
    """

    duplicate_full = df.duplicated(keep = False)
    duplicate_id = df.duplicated(
        subset = ["listing_id"],
        keep = False
        )

    return pd.DataFrame({
        "duplicate_full_row": duplicate_full,
        "duplicate_listing_id": duplicate_id
    })


def clean_price(price):
    """
    Chuyển Series giá gốc thành Series numeric, giữ nguyên index.

    Bỏ ký hiệu $ và dấu phẩy trước khi chuyển kiểu. Giá trị thiếu
    hoặc không chuyển đổi được trở thành giá trị thiếu trong kết quả.
    """
    cleaned = price.astype("string").str.replace("$","").str.replace(",","")
    return pd.to_numeric(cleaned, errors = "coerce")


def check_price(raw_price, qa_cfg=None, room_type=None):
    """
    Tạo giá numeric và các cờ QA từ Series raw_price của một mốc.

    Trả về price_cad cùng các cờ thiếu giá (missing_price), lỗi chuyển
    kiểu, giá không dương, giá hợp lệ và ngoại lai, giữ nguyên index.
    Giá hợp lệ là giá không thiếu và > 0. Theo Bài 10 §2, khi có cột
    room_type thì ngưỡng IQR được tính riêng cho từng loại chỗ ở (các
    nhóm có < 4 giá hợp lệ hoặc thiếu room_type fallback về ngưỡng toàn mốc),
    kết hợp với trần cấu hình qa.price_max.
    Hàm không xóa dòng hoặc thay đổi Series giá gốc.
    """
    settings = {**DEFAULT_QA_CONFIG, **(qa_cfg or {})}
    iqr_mult = float(settings["iqr_multiplier"])
    price_max = settings.get("price_max")
    price = clean_price(raw_price)
    price_valid = price.notna() & (price > 0)

    valid_prices = price[price_valid]
    global_q1 = valid_prices.quantile(0.25)
    global_q3 = valid_prices.quantile(0.75)
    global_iqr = global_q3 - global_q1
    global_low = global_q1 - iqr_mult * global_iqr
    global_high = global_q3 + iqr_mult * global_iqr

    if room_type is not None:
        valid_df = pd.DataFrame({"price": price, "room_type": room_type}).loc[price_valid]
        grouped = valid_df.groupby("room_type")["price"]
        counts = grouped.count()
        q1_map = grouped.quantile(0.25)
        q3_map = grouped.quantile(0.75)
        iqr_map = q3_map - q1_map
        low_map = (q1_map - iqr_mult * iqr_map).where(counts >= 4, global_low)
        high_map = (q3_map + iqr_mult * iqr_map).where(counts >= 4, global_high)
        row_low = room_type.map(low_map).fillna(global_low)
        row_high = room_type.map(high_map).fillna(global_high)
        iqr_out = (price < row_low) | (price > row_high)
    else:
        iqr_out = (price < global_low) | (price > global_high)

    if price_max is not None:
        iqr_out = iqr_out | (price > float(price_max))
    outlier = price_valid & iqr_out

    return pd.DataFrame({
        "price_cad": price,
        "missing_price": raw_price.isna(),
        "wrong_price_type": raw_price.notna() & price.isna(),
        "invalid_price": price <= 0,
        "price_valid": price_valid,
        "price_outlier": outlier,
    })


def check_numeric_rules(df, qa_cfg=None):
    """
    Kiểm tra ràng buộc số đêm và số ngày available trong listings.

    Chuyển minimum_nights, maximum_nights và availability_365 sang
    numeric để so sánh, giữ nguyên dữ liệu đầu vào. Theo Bài 10 §4,
    tách riêng cờ thiếu minimum_nights (missing_minimum_nights) khỏi
    cờ ngoài miền (invalid_minimum_nights: <= 0 hoặc > min_nights_cap).
    """
    settings = {**DEFAULT_QA_CONFIG, **(qa_cfg or {})}
    min_cap = settings.get("min_nights_cap")
    minimum_nights = pd.to_numeric(df["minimum_nights"], errors="coerce")
    maximum_nights = pd.to_numeric(df["maximum_nights"], errors="coerce")
    availability_365 = pd.to_numeric(df["availability_365"], errors="coerce")

    missing_minimum_nights = minimum_nights.isna()
    invalid_min = minimum_nights <= 0
    if min_cap is not None:
        invalid_min = invalid_min | (minimum_nights > float(min_cap))
    invalid_minimum_nights = invalid_min.fillna(False)
    invalid_maximum_nights = (maximum_nights <= 0).fillna(False)
    min_greater_max = (minimum_nights > maximum_nights).fillna(False)
    invalid_availability_365 = (
        (availability_365 < 0) | (availability_365 > 365)
    ).fillna(False)
    return pd.DataFrame({
        "missing_minimum_nights": missing_minimum_nights,
        "invalid_minimum_nights": invalid_minimum_nights,
        "invalid_maximum_nights": invalid_maximum_nights,
        "min_greater_max": min_greater_max,
        "invalid_availability_365": invalid_availability_365,
    })


def check_rating(df):
    """Xác định điểm đánh giá hợp lệ trong listings theo Bài 10 §2.

    Tách rõ giá trị thiếu (missing_rating) khỏi giá trị nằm ngoài miền
    [0, 5] (invalid_rating = notna & ~between(0, 5)). Không tự điền 0.
    """
    rating = pd.to_numeric(df["review_scores_rating"], errors="coerce")
    missing_rating = rating.isna()
    invalid_rating = rating.notna() & ~rating.between(0, 5)
    rating_valid = rating.notna() & rating.between(0, 5)
    return pd.DataFrame({
        "missing_rating": missing_rating,
        "rating_valid": rating_valid,
        "invalid_rating": invalid_rating,
    })


def check_categories(df, qa_cfg=None):
    """
    Kiểm tra danh mục room_type và analysis_area trong listings.

    Trả về hai cột boolean cùng index với df; True nghĩa là hợp lệ
    theo danh sách qa.room_types (kèm chuẩn hóa room_aliases nếu có)
    và qa.valid_areas trong cấu hình.
    """
    settings = {**DEFAULT_QA_CONFIG, **(qa_cfg or {})}
    valid_area = list(settings.get("valid_areas") or DEFAULT_QA_CONFIG["valid_areas"])
    allowed_rooms = list(settings.get("room_types") or DEFAULT_QA_CONFIG["room_types"])
    aliases = settings.get("room_aliases") or {}
    room_series = df["room_type"].astype("string").str.strip()
    normalized_room = room_series.str.lower().map(aliases).fillna(room_series)
    room_type_valid = normalized_room.notna() & normalized_room.isin(allowed_rooms)
    analysis_area_valid = df["analysis_area"].isin(valid_area)
    return pd.DataFrame({
        "room_type_valid": room_type_valid,
        "analysis_area_valid" : analysis_area_valid,
        "category_mismatch": ~(room_type_valid & analysis_area_valid),
    })


def diff_room_type(df1,df2):
    """Compare room_type for listings present in both snapshots."""
    merged = df1.merge(
        df2,
        on = "listing_id",
        suffixes = ("_1","_2"),
        how = "inner"
    )
    merged["room_change"] = (
        merged["room_type_1"] != merged["room_type_2"]
    )
    return merged[
        ["listing_id", "room_type_1", "room_type_2", "room_change"]
    ]


def run_qa_listings(df, qa_cfg=None):
    """Tổng hợp các kiểm tra listings đã chuẩn bị của một mốc.

    Trả về dict gồm missing_summary và row_flags, tổng hợp kiểm tra
    trùng, giá (IQR theo room_type), ràng buộc numeric, danh mục và điểm đánh giá.
    Các cột cờ giữ index của df; hàm không lọc dòng hoặc lưu file.
    """
    validate_schema(
        df,
        ["listing_id", "price", "minimum_nights", "maximum_nights", "availability_365", "room_type", "analysis_area", "review_scores_rating"],
        "listings",
    )
    # 1. Gọi các hàm kiểm tra
    missing_summary = check_missing(df)
    duplicate_flags = check_duplicates(df)
    price_flags = check_price(df["price"], qa_cfg=qa_cfg, room_type=df["room_type"])
    numeric_flags = check_numeric_rules(df, qa_cfg=qa_cfg)
    category_flags = check_categories(df, qa_cfg=qa_cfg)
    rating_flags = check_rating(df)
    missing_id_flags = missing_listing_id(df)
    duplicate_flags["duplicate_listing"] = (
        duplicate_flags["duplicate_listing_id"] & ~missing_id_flags["missing_listing_id"]
    )
    duplicate_flags["duplicate_listing_full_row"] = duplicate_flags["duplicate_full_row"]
    # 2. Ghép các bảng cờ theo chiều ngang
    row_flags = pd.concat(
        [duplicate_flags, price_flags, numeric_flags, category_flags, rating_flags, missing_id_flags],
        axis=1,
    )
    # 3. Gom kết quả thành report
    report = {
        "missing_summary": missing_summary,
        "row_flags": row_flags,
    }

    return report


def process_listings(date, phan_cong, raw_dir, *, processed_dir=None, report_rows=None, qa_cfg=None, long_stay_nights=30):
    """Đọc, chuẩn bị, chạy QA và lưu listings của một mốc.

    Trả về listings_clean để reviews và calendar đối chiếu trực tiếp.
    """
    df = pd.read_csv(
        raw_dir / date / "listings.csv.gz",
        dtype={"id": "string"},
    )
    validate_schema(df, ["id", "price", "room_type", "minimum_nights", "maximum_nights", "review_scores_rating"], f"listings ({date})")
    for column in ("neighbourhood_cleansed", "availability_365"):
        if column not in df:
            df[column] = pd.NA
    if df["neighbourhood_cleansed"].isna().all():
        df["neighbourhood_cleansed"] = df["id"].map(
            phan_cong.dropna(subset=["listing_id"]).drop_duplicates("listing_id")
            .set_index("listing_id")["analysis_area"]
        )
    prepare = prepare_listings(df,phan_cong,date)
    report = run_qa_listings(prepare, qa_cfg=qa_cfg)
    row_flags = report["row_flags"]
    all_data = pd.concat(
    [
        prepare.reset_index(drop=True),
        row_flags.reset_index(drop=True)
    ],
    axis=1
    )
    listings_clean = all_data[
        [
            "snapshot_date",
            "listing_id",
            "neighbourhood_cleansed",
            "room_type",
            "price_cad",
            "price_valid",
            "price_outlier",
            "room_type_valid",
            "review_scores_rating",
            "rating_valid",
            "latitude",
            "longitude",
            "last_scraped",
            "availability_365",
            "number_of_reviews",
            "missing_price",
            "analysis_area",
            "price",
            "minimum_nights",
            "maximum_nights",
        ]
        + [col for col in row_flags.columns if col not in {
            "price_cad", "price_valid", "price_outlier", "room_type_valid",
            "rating_valid", "missing_price"
        }]
    ].copy()
    report_table(report_rows, date, "listings", prepare, listings_clean, row_flags, long_stay_nights=long_stay_nights)
    output_dir = (processed_dir if processed_dir is not None else DATA_DIR / "processed") / date

    output_dir.mkdir(
                parents=True,
                exist_ok=True
            )

    # 7. Lưu file
    listings_clean.to_csv(
                output_dir / "listings_clean.csv",
                index = False)
    logging.info("QA listings %s: shape=%s, unique=%d", date, listings_clean.shape, listings_clean["listing_id"].nunique())
    return listings_clean



# ============================================================================
# 3. REVIEWS: CHUẨN BỊ, KIỂM TRA, SO SÁNH VÀ XỬ LÝ
# ============================================================================

def prepare_reviews(raw_reviews, phan_cong, snapshot_date):
    """Lọc reviews theo review_id được giao trong bảng phân công.

    Nhận reviews gốc có cột id và bảng phân công có review_id.
    Trả về bản sao các review khớp, đổi id thành review_id và thêm
    snapshot_date. Hàm lọc theo mã review, không lọc theo mã listing.
    """
    mask = raw_reviews["id"].isin(phan_cong["review_id"].dropna())
    bang_moi = raw_reviews[mask].copy()
    bang_moi = bang_moi.rename(
        columns={"id": "review_id"}
    )
    bang_moi["snapshot_date"] = snapshot_date
    return bang_moi


def check_duplicate_review(reviews_df):
    """Đánh dấu review trùng toàn dòng hoặc trùng review_id.

    Nhận reviews của một mốc. Trả về duplicate_all và duplicate_id
    cùng index với đầu vào. True đánh dấu tất cả dòng thuộc nhóm
    trùng; hàm không xóa review.
    """
    duplicate_all = reviews_df.duplicated(keep = False)
    duplicate_id = reviews_df.duplicated(
        subset = "review_id",
        keep = False
    )
    return pd.DataFrame({
        "duplicate_all" : duplicate_all,
        "duplicate_id" : duplicate_id
    })


def comment_markup(reviews_df):
    """Phát hiện HTML và tạo bản sạch từ cột comments, giữ nguyên index.

    Giữ nguyên bình luận gốc; giải mã HTML, thay thẻ bằng khoảng trắng
    và chuẩn hóa khoảng trắng trong comment_clean.
    """
    cmt = reviews_df["comments"].fillna("").astype("string")
    cmt_markup = cmt.str.contains(TAG,regex = True)
    decoded = cmt.map(html.unescape)
    clean = decoded.str.replace(
    r"<br\s*/?>",
    " ",
    regex=True,
    case=False
    )
    clean = (
    clean
    .str.replace(TAG, " ", regex=True)
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
    )
    return pd.DataFrame({
        "comment_markup": cmt_markup,
        "comment_clean": clean,
    })


def check_comments(reviews_df):
    """Làm sạch HTML rồi kiểm tra bình luận còn nội dung hay không.

    Trả về comment_markup, comment_clean, comment_empty và text_valid
    cùng index với đầu vào. Bình luận thiếu hoặc chỉ chứa thẻ/khoảng
    trắng có comment_empty=True và text_valid=False. Không lọc dòng
    hoặc áp dụng ngưỡng độ dài tối thiểu.
    """
    flags = comment_markup(reviews_df)
    flags["comment_empty"] = flags["comment_clean"].eq("")
    flags["text_valid"] = ~flags["comment_empty"]
    return flags


def check_review_date(reviews_df,listings_df):
    """Gắn cờ ngày review sau last_scraped của listing cùng mốc.

    Chỉ đối chiếu listing_id không thiếu và duy nhất. Chỉ so sánh phần
    ngày khi cả hai ngày đọc được; giữ index của reviews. Khóa trùng,
    thiếu ngày thu thập hoặc không khớp listing thì chưa kết luận.
    """
    review_date = check_date(reviews_df)["date_parsed"]
    unique_listings = listings_df.loc[
        ~missing_listing_id(listings_df)["missing_listing_id"]
        & ~listings_df["listing_id"].duplicated(keep=False)
    ]
    scraped_lookup = unique_listings.set_index("listing_id")["last_scraped"]
    scraped_date = pd.to_datetime(
        reviews_df["listing_id"].map(scraped_lookup), errors="coerce"
    )
    review_after_scrape = (
        review_date.notna()
        & scraped_date.notna()
        & (review_date.dt.normalize() > scraped_date.dt.normalize())
    )
    return pd.DataFrame({"review_after_scrape": review_after_scrape})


def check_common_reviews(df1, df2):
    common_reviews = df1.merge(
        df2,
        on="review_id",
        how="inner",
        suffixes=("_1", "_2")
    )
    return common_reviews[["review_id"]].drop_duplicates()


def review_changes_date(df1,df2):
    merged = df1.merge(
        df2,
        on = "review_id",
        suffixes = ("_1","_2"),
        how = "inner"
    )
    merged["date_changed"] = (
        merged["date_1"] != merged["date_2"]
    )
    return merged[["review_id", "date_1", "date_2", "date_changed"]]


def check_review_listing_changed(df1, df2):
    merged = df1.merge(
    df2,
    on="review_id",
    suffixes=("_1", "_2"),
    how="inner"
    )

    merged["listing_changed"] = (
        merged["listing_id_1"] != merged["listing_id_2"]
    )
    return merged[["review_id", "listing_id_1", "listing_id_2", "listing_changed"]]


def check_same_comments(df1,df2):
    merged = df1.merge(
        df2,
        on = "review_id",
        suffixes = ("_1","_2"),
        how = "inner"
    )
    merged["same_comments"] = (merged["comments_1"] == merged["comments_2"])
    return merged[["review_id", "same_comments"]]


def run_qa_reviews(reviews_df,raw_listings):
    """Tổng hợp QA reviews của một mốc, giữ nguyên các dòng đầu vào.

    Nhận reviews đã chuẩn bị và listings cùng mốc có listing_id.
    Trả về dict gồm missing_summary và row_flags, tổng hợp kiểm tra
    trùng review, HTML và nội dung sau làm sạch, ngày và liên kết listing.
    Hàm không tự lưu báo cáo hoặc chọn mẫu LLM.
    """
    missing_summary = check_missing(reviews_df)
    duplicate_reviews_flags = check_duplicate_review(reviews_df)
    comments_reviews_flags = check_comments(reviews_df)
    listing_match_flags = check_listing_match(reviews_df, raw_listings)
    date_reviews_flags = check_date(reviews_df)
    review_date_flags = check_review_date(reviews_df, raw_listings)
    missing_id_flags = missing_listing_id(reviews_df)
    review_id = reviews_df["review_id"].astype("string").str.strip()
    missing_review_flags = pd.DataFrame({
        "missing_review_id": review_id.isna() | review_id.eq("").fillna(False)
    })
    duplicate_reviews_flags = duplicate_reviews_flags.rename(columns={
        "duplicate_all": "duplicate_review_full_row",
        "duplicate_id": "duplicate_review_id",
    })
    duplicate_reviews_flags["duplicate_review_id"] &= ~missing_review_flags["missing_review_id"]
    row_flags = pd.concat(
        [
        duplicate_reviews_flags,
        comments_reviews_flags,
        date_reviews_flags,
        review_date_flags,
        missing_id_flags,
        missing_review_flags,
        listing_match_flags
        ],
        axis = 1
    )
    report = {
        "missing_summary":  missing_summary ,
        "row_flags": row_flags 
    }

    return report


def process_reviews(date, phan_cong, listings_df, *, raw_dir=None,
                    processed_dir=None, report_rows=None):
    """Đọc, chuẩn bị, chạy QA và lưu reviews của một mốc.

    Dùng listings_df cùng mốc để kiểm tra liên kết, trả về reviews_clean.
    """
    # 1. Đọc reviews raw và kiểm tra cấu trúc đầu vào
    raw_reviews = pd.read_csv(
        (raw_dir if raw_dir is not None else RAW_DIR) / date / "reviews.csv.gz",
        dtype={"id": "string", "listing_id": "string"},
    )
    validate_schema(raw_reviews, ["id", "listing_id", "date", "comments"], f"reviews ({date})")


    # 3. Lọc reviews thuộc 1000 listings của nhóm
    prepared_reviews = prepare_reviews(
        raw_reviews,
        phan_cong,
        date
    )

    # 4. Chạy QA reviews
    review_report = run_qa_reviews(
        prepared_reviews,
        listings_df
    )
    review_flags = review_report["row_flags"]

    # 5. Ghép reviews + QA flags
    all_reviews = pd.concat(
        [
            prepared_reviews.reset_index(drop=True),
            review_flags.reset_index(drop=True)
        ],
        axis=1
    )

    # 6. Tạo reviews_clean
    reviews_clean = all_reviews[
        [
            "snapshot_date",
            "review_id",
            "listing_id",
            "date_parsed",
            "comments",
            "comment_markup",
            "comment_clean",
            "comment_empty",
            "missing_review_id",
            "missing_listing_id",
            "duplicate_review_full_row",
            "duplicate_review_id",
            "date_missing",
            "wrong_date_type",
            "date_valid",
            "review_after_scrape",
            "listing_not_found",
            "text_valid",
            "listing_match"
        ]
    ].copy()

    # đổi date_parsed về tên date cho output cuối
    reviews_clean = reviews_clean.rename(
        columns={"date_parsed": "date"}
    )
    # 7. Folder output
    report_table(report_rows, date, "reviews", prepared_reviews, reviews_clean, review_flags)
    output_dir = (processed_dir if processed_dir is not None else DATA_DIR / "processed") / date
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )
    # 8. Lưu reviews_clean
    reviews_clean.to_csv(
        output_dir / "reviews_clean.csv",
        index=False
    )
    unmatched = reviews_clean.loc[
        ~reviews_clean["listing_match"], "listing_id"
    ]
    logging.info("QA reviews %s: shape=%s, unique=%d, unmatched_listings=%d", date, reviews_clean.shape, reviews_clean["review_id"].nunique(), unmatched.nunique())
    return reviews_clean



# ============================================================================
# 4. CALENDAR: CHUẨN BỊ, KIỂM TRA, TỔNG HỢP VÀ XỬ LÝ
# ============================================================================

def prepare_calendar(raw_calendar,phan_cong,snapshot):
    """Chuẩn bị calendar cho các listing được phân công tại một mốc.

    Hai bảng đầu vào cần có listing_id. Lọc calendar theo mã listing
    trong phan_cong và trả về bản sao có thêm snapshot_date.
    """
    mask = raw_calendar["listing_id"].isin(phan_cong["listing_id"])
    raw_calendar = raw_calendar[mask]
    bang_moi = raw_calendar.copy()
    bang_moi["snapshot_date"] = snapshot
    return bang_moi


def check_duplicate_calendar(calendar_df):
    """Đánh dấu bản ghi calendar trùng trong một mốc.

    Trả về duplicate_full_row và duplicate_listing_date cùng index
    với đầu vào. Cờ thứ hai kiểm tra cặp (listing_id, date) gốc,
    chưa chuyển kiểu ngày. True đánh dấu tất cả dòng thuộc nhóm trùng.
    """
    duplicate_all = calendar_df.duplicated(keep = False)
    duplicate_date = calendar_df.duplicated(
        subset = ["listing_id","date"],
        keep = False
    )
    return pd.DataFrame({
            "duplicate_full_row": duplicate_all,
            "duplicate_listing_date": duplicate_date
        })


def check_available(calendar_df):
    """Chuẩn hóa và kiểm tra trạng thái available của calendar.

    Chuyển cột available sang chuỗi, bỏ khoảng trắng đầu/cuối và
    chuyển chữ thường. Trả về available_clean, available_valid
    (chấp nhận t, f, true, false) và available_true (t hoặc true),
    cùng index với đầu vào. Giá trị thiếu không được coi là hợp lệ.
    """
    available_clean = calendar_df["available"].astype("string").str.strip().str.lower()
    available_valid = available_clean.isin(["t", "f", "true", "false"])
    available_true = available_clean.isin(["t", "true"])
    return pd.DataFrame({
            "available_clean": available_clean,
            "available_valid": available_valid,
            "available_true": available_true
        })


def missing_available(calendar_df):
    """Gắn cờ available bị null, rỗng hoặc chỉ có khoảng trắng."""
    available_parsed = calendar_df["available"].astype('string').str.strip().str.lower()
    missing_available = available_parsed.isna() | available_parsed.eq("").fillna(False)
    return pd.DataFrame({
        "missing_available" : missing_available
    })


def invalid_available(calendar_df):
    """Gắn cờ trạng thái ngoài t/f/true/false, bao gồm cả thiếu."""
    available_clean = calendar_df["available"].astype("string").str.strip().str.lower()
    invalid_available = (~available_clean.isin(["t","f","true","false"]))
    return pd.DataFrame({
        "invalid_available" : invalid_available
    })


def calendar_available_conflict(calendar_df):
    """Gắn cờ nhóm listing/ngày có cả hai trạng thái trong cùng mốc."""
    state = (
    calendar_df["available"]
    .astype("string")
    .str.strip()
    .str.lower()
    .map({"t": True, "true": True, "f": False, "false": False})
    )
    date = check_date(calendar_df)["date_parsed"].dt.normalize()

    group_keys = [calendar_df["listing_id"], date]
    if "snapshot_date" in calendar_df.columns:
        group_keys.insert(0, calendar_df["snapshot_date"])
    n_states = state.groupby(group_keys).transform("nunique")

    conflict = n_states.eq(2) & ~missing_listing_id(calendar_df)["missing_listing_id"]
    return pd.DataFrame({"calendar_available_conflict": conflict})


def run_qa_calendar(calendar_df, listings_df):
    """Tổng hợp kiểm tra calendar và liên kết listings trong cùng mốc.

    Nhận calendar đã chuẩn bị và listings có listing_id. Trả về dict
    gồm missing_summary theo cột và row_flags theo dòng: trùng,
    ngày, trạng thái available và khớp listing. Không lọc hay lưu file.
    """
    missing_summary = check_missing(calendar_df)

    duplicate_flags = check_duplicate_calendar(calendar_df)
    date_flags = check_date(calendar_df)
    duplicate_keys = pd.DataFrame({
        "listing_id": calendar_df["listing_id"],
        "date": date_flags["date_parsed"].dt.normalize(),
    })
    valid_keys = (
        ~missing_listing_id(calendar_df)["missing_listing_id"]
        & date_flags["date_valid"]
    )
    duplicate_flags["duplicate_calendar"] = duplicate_keys.duplicated(keep=False) & valid_keys
    duplicate_flags["duplicate_calendar_full_row"] = duplicate_flags["duplicate_full_row"]
    available_flags = check_available(calendar_df)
    invalid_available_flags = invalid_available(calendar_df)
    missing_available_flags = missing_available(calendar_df)
    conflict_flags = calendar_available_conflict(calendar_df)
    missing_id_flags = missing_listing_id(calendar_df)
    listing_match_flags = check_listing_match(calendar_df, listings_df)

    row_flags = pd.concat(
        [
            duplicate_flags,
            date_flags,
            available_flags,
            invalid_available_flags,
            missing_available_flags,
            conflict_flags,
            missing_id_flags,
            listing_match_flags
        ],
        axis=1
    )
    report = {
            "missing_summary":  missing_summary ,
            "row_flags": row_flags 
        }

    return report


def calendar_listing_summary(calendar_qa_df):
    """Tổng hợp lịch phòng đã QA thành một dòng cho mỗi listing.

    Đầu vào thuộc một mốc, có listing_id, date_parsed, available_valid
    và available_true. Gom theo listing/ngày; chỉ dùng ngày có đúng
    một dòng và trạng thái hợp lệ, thống nhất với lịch đầu vào KPI.
    Ngày trùng bị loại kể cả khi các trạng thái giống nhau.

    Trả về khoảng ngày, số ngày quan sát, số ngày trạng thái hợp lệ,
    số ngày available, availability_share (available/ngày hợp lệ) và
    coverage_share (ngày hợp lệ/365). Không có ngày hợp lệ thì
    availability_share bị thiếu; khóa nhóm bị thiếu được bỏ mặc định.
    """
    calendar_qa_df = calendar_qa_df.loc[
        ~missing_listing_id(calendar_qa_df)["missing_listing_id"]
    ].copy()
    calendar_qa_df["date_parsed"] = calendar_qa_df["date_parsed"].dt.normalize()
    daily = calendar_qa_df.groupby(
    ["listing_id", "date_parsed"],
    as_index=False
        ).agg(
            n_rows=("available_valid", "size"),
            n_valid_rows=("available_valid", "sum"),
            n_true_rows=("available_true", "sum")
        )
    daily["available_valid_day"] = (
            daily["n_rows"].eq(1)
            & (daily["n_valid_rows"] > 0)
            & (
                (daily["n_true_rows"] == 0)
                | (daily["n_true_rows"] == daily["n_valid_rows"])
            )
        )
    daily["available_true_day"] = (
            daily["available_valid_day"]
            & (daily["n_true_rows"] == daily["n_valid_rows"])
        )
    summary = daily.groupby("listing_id").agg(
        calendar_start = ("date_parsed","min"),
        calendar_end=("date_parsed", "max"),
        n_calendar_days=("date_parsed", "size"),
        n_available_valid=("available_valid_day", "sum"),
        n_available=("available_true_day", "sum")
    ).reset_index()
    summary["availability_share"] = (
    summary["n_available"] / summary["n_available_valid"]
    ).where(summary["n_available_valid"] != 0)  
    summary["coverage_share"] = (
    summary["n_available_valid"] / 365
    )
    return summary


def process_calendar(date, phan_cong, listings_df, *, raw_dir=None,
                     processed_dir=None, report_rows=None, chunksize=100_000):
    """Đọc, chạy QA và lưu calendar chi tiết của một mốc.

    Đọc từng khối và chỉ giữ listing của nhóm trước khi ghép dữ liệu.
    Chạy QA sau khi ghép để phát hiện cả dòng trùng giữa các khối.
    Dùng listings_df cùng mốc để kiểm tra liên kết, trả về lịch chi tiết
    đã chuẩn hóa cho KPI và lưu calendar_summary riêng.
    """
    # Chỉ giữ các dòng thuộc nhóm trong từng khối để giảm bộ nhớ.
    calendar_path = (raw_dir if raw_dir is not None else RAW_DIR) / date / "calendar.csv.gz"
    columns = [
        "listing_id", "date", "available", "price", "adjusted_price",
        "minimum_nights", "maximum_nights",
    ]
    # Một số mốc không cung cấp price/adjusted_price trong calendar.
    available_columns = pd.read_csv(calendar_path, nrows=0).columns
    missing_columns = {"listing_id", "date", "available"} - set(available_columns)
    if missing_columns:
        raise ValueError(f"Calendar {date} thiếu cột bắt buộc: {sorted(missing_columns)}")
    columns = [column for column in columns if column in available_columns]
    listing_ids = set(phan_cong["listing_id"].dropna())
    parts = []
    with pd.read_csv(
        calendar_path, dtype={"listing_id": "string"},
        usecols=columns, chunksize=chunksize,
    ) as reader:
        for chunk in reader:
            selected = chunk.loc[chunk["listing_id"].isin(listing_ids)].copy()
            parts.append(selected)

    prepared_calendar = (
        pd.concat(parts, ignore_index=True)
        if parts else pd.DataFrame(columns=columns).astype({"listing_id": "string"})
    )
    prepared_calendar["snapshot_date"] = date

    # 4. Chạy QA calendar
    calendar_report = run_qa_calendar(
        prepared_calendar,
        listings_df
    )

    row_flags = calendar_report["row_flags"]

    # 5. Ghép calendar với các QA flags
    calendar_qa_df = pd.concat(
        [
            prepared_calendar.reset_index(drop=True),
            row_flags.reset_index(drop=True)
        ],
        axis=1
    )

    # 6. Tạo summary theo listing
    calendar_summary = calendar_listing_summary(
        calendar_qa_df
    )

    # 7. Thêm snapshot_date
    calendar_summary.insert(
        0,
        "snapshot_date",
        date
    )

    # 8. Tạo folder output
    report_table(report_rows, date, "calendar", prepared_calendar, calendar_qa_df, row_flags)
    output_dir = (processed_dir if processed_dir is not None else DATA_DIR / "processed") / date

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Lưu bảng tổng hợp lịch theo listing tại mỗi mốc để tiết kiệm dung lượng.
    calendar_summary.to_csv(
        output_dir / "calendar_listing_summary.csv", index=False
    )

    clean_calendar = calendar_qa_df.loc[
        ~calendar_qa_df["duplicate_calendar"].fillna(False).astype(bool)
        & ~calendar_qa_df["calendar_available_conflict"].fillna(False).astype(bool),
        ["snapshot_date", "listing_id", "date_parsed", "available_clean"],
    ].rename(columns={"snapshot_date": "snapshot", "date_parsed": "date"})
    clean_calendar["available"] = clean_calendar["available_clean"].map(
        {"t": 1.0, "f": 0.0, "true": 1.0, "false": 0.0}
    )
    clean_calendar = clean_calendar.drop(columns=["available_clean"])

    # 9. Check nhanh
    logging.info("QA calendar %s: shape=%s, unique_listings=%d", date, calendar_summary.shape, calendar_summary["listing_id"].nunique())
    return clean_calendar


# ============================================================================
# 5. NEIGHBOURHOODS: XUẤT RANH GIỚI KHU VỰC
# ============================================================================

def process_neighbourhoods(date, raw_dir, processed_dir):
    """Xuất ranh giới giữ nguyên nội dung sang file neighbourhoods_cleansed."""
    source = raw_dir / date / "neighbourhoods.geojson"
    if not source.exists():
        return None
    output_dir = processed_dir / date
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "neighbourhoods_cleansed.geojson"
    shutil.copyfile(source, output)
    logging.info("NEIGHBOURHOODS: %s -> %s", date, output)
    return output



# ============================================================================
# 6. REPORT: THU KẾT QUẢ VÀ XUẤT CSV
# ============================================================================

def add_report_row(report_rows, snapshot, table, rule, checked, flagged, *,
                   compared_snapshot=None, rows_before=None, rows_after=None,
                   action="flag_only", metric_name=None, metric_before=None,
                   metric_after=None, note=""):
    """Thêm một kết quả QA; chỉ ghi số dòng xóa khi thực sự lọc dòng."""
    definition = RULES.get(rule, {})
    report_rows.append({
        "snapshot_date": snapshot,
        "compared_snapshot": compared_snapshot,
        "table": table,
        "rule": rule,
        "condition": definition.get("condition", "Xem metric_name và note"),
        "reason": definition.get("reason", "Đối chiếu dữ liệu trước và sau QA"),
        "action": action,
        "action_detail": definition.get("action", "Chỉ đo, không tự xoá dòng"),
        "rows_checked": checked,
        "rows_flagged": flagged,
        "rows_removed": (
            max(rows_before - rows_after, 0)
            if rows_before is not None and rows_after is not None else 0
        ),
        "rows_before": rows_before,
        "rows_after": rows_after,
        "metric_name": metric_name,
        "metric_before": metric_before,
        "metric_after": metric_after,
        "note": note,
    })


def report_table(report_rows, snapshot, table, before, after, flags, *, long_stay_nights=30):
    """Tổng hợp cờ gốc, trước khi mất thông tin khi chuyển kiểu/làm sạch.

    before là dữ liệu đã lọc theo phân công, chưa chạy QA. after vẫn ở
    mức dòng gốc; không dùng calendar_listing_summary để đếm dòng bị xóa.
    """
    if report_rows is None:
        return
    active_rule_cols = []
    for rule, definition in RULES.items():
        if rule == "rows_with_any_flag":
            continue
        if table in definition["table"].split(",") and rule in flags.columns:
            active_rule_cols.append(rule)
            add_report_row(
                report_rows, snapshot, table, rule,
                checked=len(before), flagged=int(flags[rule].sum()),
                rows_before=len(before), rows_after=len(after),
                action="clean_derived_column" if rule == "comment_markup" else "flag_only",
                note=(f"{definition['condition']}. {definition['action']}. "
                      "Phạm vi: dữ liệu đã lọc theo phân công; giữ các dòng."),
            )
    if active_rule_cols:
        any_flag_count = int(flags[active_rule_cols].fillna(False).astype(bool).any(axis=1).sum())
        add_report_row(
            report_rows, snapshot, table, "rows_with_any_flag",
            checked=len(before), flagged=any_flag_count,
            rows_before=len(before), rows_after=len(after),
            action="summary_only",
            note=(f"Số hàng duy nhất có ít nhất 1 cờ QA trong {len(active_rule_cols)} quy tắc của bảng {table} "
                  "(theo Bài 10 §4: phân biệt số hàng cần xem với tổng lượt gắn cờ)."),
        )

    metrics = [("row_count", len(before), len(after), "Đơn vị: dòng.")]
    if table == "listings":
        unique_listing = (
            ~missing_listing_id(after)["missing_listing_id"]
            & ~after["listing_id"].duplicated(keep=False)
        )
        valid_after = after.loc[unique_listing & after["price_valid"] & ~after["price_outlier"], "price_cad"]
        metrics.append((
            "median_price", clean_price(before["price"]).median(),
            valid_after.median(),
            "Đơn vị: tiền tệ trong config. Trước QA: trung vị giá numeric bỏ giá thiếu; "
            "sau QA: trung vị giá hợp lệ trên listing có khóa duy nhất "
            "(price_valid và không bị cờ price_outlier, khớp với KPI K1).",
        ))
        min_before = pd.to_numeric(before["minimum_nights"], errors="coerce")
        min_after = pd.to_numeric(
            after.loc[unique_listing & ~after["invalid_minimum_nights"] & ~after["min_greater_max"], "minimum_nights"],
            errors="coerce",
        )
        metrics.append((
            "long_stay_share_pct",
            float(min_before.dropna().ge(long_stay_nights).mean() * 100) if min_before.notna().any() else np.nan,
            float(min_after.dropna().ge(long_stay_nights).mean() * 100) if min_after.notna().any() else np.nan,
            f"Đơn vị: %. Tỷ lệ listing yêu cầu tối thiểu từ {long_stay_nights} đêm trở lên trước và sau lọc khóa thiếu/trùng và cờ minimum_nights (KPI K4).",
        ))
    elif table == "reviews":
        metrics.append((
            "mean_comment_length",
            before["comments"].fillna("").astype("string").str.len().mean(),
            after["comment_clean"].fillna("").astype("string").str.len().mean(),
            "Đơn vị: ký tự/review. Trung bình độ dài comments gốc so với "
            "comment_clean; bình luận thiếu được tính là 0 ký tự.",
        ))
    elif table == "calendar":
        avail_before = before["available"].astype("string").str.strip().str.lower().map(
            {"t": 1.0, "true": 1.0, "f": 0.0, "false": 0.0}
        )
        valid_cal = (
            after["available_valid"].fillna(False).astype(bool)
            & after["date_valid"].fillna(False).astype(bool)
            & after["listing_match"].fillna(False).astype(bool)
            & ~after["duplicate_calendar"].fillna(False).astype(bool)
            & ~after["calendar_available_conflict"].fillna(False).astype(bool)
        )
        avail_after = after.loc[valid_cal, "available_true"].astype(float)
        metrics.append((
            "unavailable_rate_pct",
            float((1.0 - avail_before.dropna().mean()) * 100) if avail_before.notna().any() else np.nan,
            float((1.0 - avail_after.mean()) * 100) if len(avail_after) else np.nan,
            "Đơn vị: %. Tỷ lệ ngày không khả dụng trước và sau khi loại ngày/trạng thái không hợp lệ, "
            "listing không khớp và dòng trùng/mâu thuẫn trạng thái; KPI K2 lọc thêm listing có khóa duy nhất và có khu vực.",
        ))
    for name, value_before, value_after, note in metrics:
        if pd.isna(value_before) or pd.isna(value_after):
            note += " Không có quan sát đủ điều kiện tính ở phía có metric trống; không thay bằng 0."
        add_report_row(
            report_rows, snapshot, table, "metric_before_after",
            checked=len(before), flagged=0,
            rows_before=len(before), rows_after=len(after), action="measure_only",
            metric_name=name, metric_before=value_before, metric_after=value_after,
            note="Trước/sau QA trên cùng phạm vi phân công. " + note,
        )


def report_review_snapshots(report_rows, reviews_by_snapshot):
    """So sánh từng cặp mốc; chỉ so sánh thuộc tính của ID duy nhất."""
    for snapshot_1, snapshot_2 in combinations(reviews_by_snapshot, 2):
        df1 = reviews_by_snapshot[snapshot_1]
        df2 = reviews_by_snapshot[snapshot_2]
        ids = []
        unique_tables = []
        for df in (df1, df2):
            valid_id = df["review_id"].notna() & df["review_id"].str.strip().ne("")
            ids.append(df.loc[valid_id, ["review_id"]].drop_duplicates())
            unique_tables.append(df.loc[
                valid_id & ~df["review_id"].duplicated(keep=False),
                ["review_id", "listing_id", "date", "comments"],
            ].copy())

        common = check_common_reviews(*ids)
        add_report_row(
            report_rows, snapshot_1, "reviews", "review_id_repeated",
            checked=len(ids[0]), flagged=len(common),
            compared_snapshot=snapshot_2, action="record_only",
            note="ID không thiếu, duy nhất ở mốc 1 xuất hiện ở mốc 2; "
                 "xuất hiện lại không mặc định là lỗi; giữ các dòng.",
        )

        date_tables, listing_tables, comment_tables = [], [], []
        for df in unique_tables:
            dates = pd.to_datetime(df["date"], errors="coerce", format="mixed").dt.normalize()
            date_table = df.loc[dates.notna(), ["review_id"]].copy()
            date_table["date"] = dates.loc[date_table.index]
            date_tables.append(date_table)
            valid_listing = ~missing_listing_id(df)["missing_listing_id"]
            listing_tables.append(df.loc[valid_listing, ["review_id", "listing_id"]])
            # Hai phía phải có comments gốc; chuỗi rỗng vẫn là nội dung để so sánh.
            comment_tables.append(df.loc[df["comments"].notna(), ["review_id", "comments"]])

        changed_dates = review_changes_date(*date_tables)
        changed_listings = check_review_listing_changed(*listing_tables)
        comments = check_same_comments(*comment_tables)
        results = [
            ("date_changed", len(changed_dates), int(changed_dates["date_changed"].sum()),
             "Ngày hợp lệ, chuẩn hóa về ngày ở cả hai mốc."),
            ("listing_changed", len(changed_listings), int(changed_listings["listing_changed"].sum()),
             "listing_id không thiếu ở cả hai mốc."),
            ("comments_changed", len(comments), int((~comments["same_comments"]).sum()),
             "So sánh comments gốc, loại cặp thiếu comments; không chuẩn hóa nội dung."),
        ]
        for rule, checked, flagged, note in results:
            add_report_row(
                report_rows, snapshot_1, "reviews", rule,
                checked=checked, flagged=flagged, compared_snapshot=snapshot_2,
                note="Chỉ ID không thiếu, xuất hiện đúng một lần trong mỗi mốc. " + note,
            )


def report_listing_snapshots(report_rows, listings_by_snapshot):
    """So sánh loại phòng (room_type) của cùng listing giữa các cặp mốc."""
    for snapshot_1, snapshot_2 in combinations(listings_by_snapshot, 2):
        df1 = listings_by_snapshot[snapshot_1]
        df2 = listings_by_snapshot[snapshot_2]
        u1 = df1.loc[
            ~missing_listing_id(df1)["missing_listing_id"]
            & ~df1["listing_id"].duplicated(keep=False),
            ["listing_id", "room_type"],
        ]
        u2 = df2.loc[
            ~missing_listing_id(df2)["missing_listing_id"]
            & ~df2["listing_id"].duplicated(keep=False),
            ["listing_id", "room_type"],
        ]
        changes = diff_room_type(u1, u2)
        add_report_row(
            report_rows, snapshot_1, "listings", "room_change",
            checked=len(changes), flagged=int(changes["room_change"].sum()),
            compared_snapshot=snapshot_2, action="record_only",
            note="Cùng listing_id xuất hiện duy nhất ở cả hai mốc nhưng room_type thay đổi; giữ các dòng.",
        )


def export_cross_snapshot_duplicates(listings_by_snapshot, reviews_by_snapshot, reports_dir):
    """Xuất thống kê ID lặp lại giữa các mốc ra cross_snapshot_duplicates.csv."""
    rows = []
    for table, by_snap, col in (
        ("listings", listings_by_snapshot, "listing_id"),
        ("reviews", reviews_by_snapshot, "review_id"),
    ):
        for s1, s2 in combinations(by_snap, 2):
            ids1 = set(by_snap[s1][col].dropna())
            ids2 = set(by_snap[s2][col].dropna())
            rows.append({
                "table": table,
                "snapshot_1": s1,
                "snapshot_2": s2,
                "count_1": len(ids1),
                "count_2": len(ids2),
                "shared_ids": len(ids1 & ids2),
            })
    output = reports_dir / "cross_snapshot_duplicates.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8-sig")
    return output


def export_data_dictionary(listings_df, reviews_df, calendar_df, reports_dir):
    """Tạo từ điển dữ liệu (data_dictionary.csv) cho ba bảng sạch sau QA."""
    descriptions = {
        "snapshot_date": "Ngày mốc chụp dữ liệu (YYYY-MM-DD)",
        "snapshot": "Ngày mốc chụp dữ liệu (YYYY-MM-DD)",
        "listing_id": "Mã định danh chỗ ở (chuỗi ký tự)",
        "review_id": "Mã định danh đánh giá (chuỗi ký tự)",
        "neighbourhood_cleansed": "Tên khu vực hành chính đã chuẩn hóa của Inside Airbnb",
        "analysis_area": "Mã vùng phân tích hình chữ nhật của nhóm (A01-A08)",
        "room_type": "Loại phòng (Entire home/apt, Private room, ...)",
        "price_cad": "Giá phòng mỗi đêm đã chuẩn hóa sang số thực",
        "price": "Giá gốc dạng chuỗi trong dữ liệu nguồn",
        "price_valid": "Cờ giá hợp lệ (không thiếu và > 0)",
        "price_outlier": "Cờ giá ngoại lai theo quy tắc IQR tính riêng từng room_type kết hợp trần qa.price_max",
        "missing_price": "Cờ thiếu giá niêm yết gốc",
        "wrong_price_type": "Cờ lỗi định dạng giá không chuyển được sang số",
        "invalid_price": "Cờ giá <= 0",
        "missing_minimum_nights": "Cờ thiếu minimum_nights tách riêng khỏi cờ ngoài miền",
        "minimum_nights": "Số đêm lưu trú tối thiểu",
        "maximum_nights": "Số đêm lưu trú tối đa",
        "availability_365": "Số ngày còn trống trong 365 ngày tới theo bảng listings",
        "number_of_reviews": "Tổng số lượng đánh giá tích lũy của listing",
        "review_scores_rating": "Điểm đánh giá trung bình của listing [0, 5]",
        "missing_rating": "Cờ thiếu điểm đánh giá (tách riêng khỏi điểm ngoài miền [0, 5])",
        "invalid_rating": "Cờ điểm đánh giá không thiếu nhưng nằm ngoài [0, 5]",
        "latitude": "Vĩ độ địa lý của listing",
        "longitude": "Kinh độ địa lý của listing",
        "last_scraped": "Ngày thu thập bản ghi thực tế",
        "date": "Ngày của đánh giá hoặc ngày lịch đã chuẩn hóa datetime",
        "comments": "Nội dung đánh giá văn bản gốc",
        "comment_clean": "Nội dung đánh giá sau khi gỡ thẻ HTML và chuẩn hóa khoảng trắng",
        "comment_markup": "Cờ đánh giá gốc có chứa thẻ HTML",
        "comment_empty": "Cờ đánh giá rỗng sau khi làm sạch",
        "text_valid": "Cờ đánh giá có nội dung hợp lệ để phân tích",
        "available": "Trạng thái phòng trống quy đổi số (1.0 = trống, 0.0 = không trống)",
    }
    rows = []
    for table_name, df in (
        ("listings_clean", listings_df),
        ("reviews_clean", reviews_df),
        ("calendar_clean", calendar_df),
    ):
        for col in df.columns:
            rows.append({
                "table": table_name,
                "column": col,
                "dtype": str(df[col].dtype),
                "non_null_count": int(df[col].notna().sum()),
                "null_count": int(df[col].isna().sum()),
                "description": descriptions.get(col, f"Cột kiểm tra QA / cờ trạng thái ({col})"),
            })
    output = reports_dir / "data_dictionary.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8-sig")
    return output


def export_qa_report(report_rows, reports_dir):
    """Xuất một lần sau khi hoàn tất tất cả các mốc và các cặp so sánh."""
    output = reports_dir / "qa_report.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows).to_csv(output, index=False, encoding="utf-8-sig")
    logging.info("QA REPORT: %d dòng -> %s", len(report_rows), output)
    return output



# ============================================================================
# 7. MAIN: CHẠY TOÀN BỘ CÁC MỐC
# ============================================================================

def run(cfg):
    """Chạy QA theo cấu hình của pipeline, không gắn cứng thành phố hay mốc."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.download import path
    raw_dir = path(cfg, "raw")
    processed_dir = path(cfg, "processed")
    reports_dir = path(cfg, "reports")
    listings = pd.read_csv(cfg["_root"] / cfg["inputs"]["listing_ids"], dtype={"id": "string"})
    reviews = pd.read_csv(cfg["_root"] / cfg["inputs"]["review_ids"], dtype={"id": "string"})
    areas_path = cfg["_root"] / cfg["inputs"]["areas"]
    valid_areas = pd.read_csv(areas_path, dtype=str)["area"].dropna().tolist() if areas_path.exists() else DEFAULT_QA_CONFIG["valid_areas"]
    qa_cfg = {**DEFAULT_QA_CONFIG, **cfg.get("qa", {}), "valid_areas": cfg.get("qa", {}).get("valid_areas", valid_areas)}
    long_stay_nights = cfg.get("kpi", {}).get("long_stay_nights", 30)
    listings_assign = listings[["id", "analysis_area"]].rename(columns={"id": "listing_id"}).copy()
    reviews_assign = reviews[["id"]].rename(columns={"id": "review_id"}).copy()
    snapshots = cfg["snapshots"]
    report_rows = []
    listings_by_snapshot = {}
    reviews_by_snapshot = {}
    calendar_blocks = []
    for date in snapshots:
        listings_df = process_listings(
            date, listings_assign, raw_dir, processed_dir=processed_dir,
            report_rows=report_rows, qa_cfg=qa_cfg, long_stay_nights=long_stay_nights,
        )
        listings_by_snapshot[date] = listings_df
        reviews_by_snapshot[date] = process_reviews(
            date, reviews_assign, listings_df, raw_dir=raw_dir,
            processed_dir=processed_dir, report_rows=report_rows,
        )
        calendar_blocks.append(process_calendar(
            date, listings_assign, listings_df, raw_dir=raw_dir,
            processed_dir=processed_dir, report_rows=report_rows,
            chunksize=cfg["io"]["chunksize"],
        ))
        process_neighbourhoods(date, raw_dir, processed_dir)
    from src.download import save
    calendar_all = pd.concat(calendar_blocks, ignore_index=True)
    save(cfg, calendar_all, "calendar_clean")
    report_listing_snapshots(report_rows, listings_by_snapshot)
    report_review_snapshots(report_rows, reviews_by_snapshot)
    export_qa_report(report_rows, reports_dir)
    export_data_dictionary(
        listings_by_snapshot[snapshots[-1]],
        reviews_by_snapshot[snapshots[-1]],
        calendar_blocks[-1],
        reports_dir,
    )


def main():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.download import cli
    cli(run)


if __name__ == "__main__":
    main()
