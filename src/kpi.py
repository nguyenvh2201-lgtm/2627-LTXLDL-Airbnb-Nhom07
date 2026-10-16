import pandas as pd
import numpy as np
import os

def run(config):
    """
    Hàm chạy tính toán KPI cho 1 snapshot.
    Yêu cầu đầu vào: Đường dẫn tới thư mục chứa dữ liệu sạch của 1 mốc.
    """
    snapshot_date = config['snapshot_date']
    input_dir = config['input_dir']
    output_dir = config['output_dir']
    
    # 1. ĐỌC DỮ LIỆU SẠCH (Từ thư mục processed)
    # Lưu ý: Code này giả định TV1/TV2 đã lưu ra định dạng .csv
    listings_path = os.path.join(input_dir, 'listings.csv')
    calendar_path = os.path.join(input_dir, 'calendar.csv')
    
    if not os.path.exists(listings_path) or not os.path.exists(calendar_path):
        print(f"Lỗi: Không tìm thấy dữ liệu sạch tại {input_dir}")
        return

    df_listings = pd.read_csv(listings_path, low_memory=False)
    df_calendar = pd.read_csv(calendar_path, low_memory=False)

    # 2. XỬ LÝ LỊCH (CALENDAR) 
    # Tính tỷ lệ trống (availability_share_mean) cho từng listing_id
    # Giả sử cột 'available' chứa 't' (true) hoặc 'f' (false)
    df_calendar['is_available'] = df_calendar['available'] == 't'
    cal_summary = df_calendar.groupby('listing_id').agg(
        availability_share_mean=('is_available', 'mean'),
        calendar_coverage_mean=('date', 'count') # Số ngày có dữ liệu
    ).reset_index()

    # Ghép bảng lịch vào listings (Quan hệ 1-1 theo yêu cầu)
    df = df_listings.merge(cal_summary, left_on='id', right_on='listing_id', how='left')

    # 3. CHUẨN BỊ CÁC CỘT TÍNH TOÁN
    # Chuyển đổi giá (price) sang dạng số (loại bỏ $ và dấu phẩy nếu TV2 chưa làm)
    if df['price'].dtype == object:
        df['price'] = df['price'].replace(r'[\$,]', '', regex=True).astype(float)
    
    # Xử lý nhãn Unknown cho khu vực và loại phòng theo yêu cầu
    df['neighbourhood_cleansed'] = df['neighbourhood_cleansed'].fillna('Unknown')
    df['room_type'] = df['room_type'].fillna('Unknown')

    # 4. HÀM TÍNH KPI CHUNG CHO BẤT KỲ NHÓM NÀO
    def calculate_metrics(group_df):
        # Lọc các dòng hợp lệ
        valid_price = group_df.dropna(subset=['price'])
        valid_rating = group_df.dropna(subset=['review_scores_rating'])
        valid_room = group_df[group_df['room_type'] != 'Unknown']
        
        # Tính toán
        res = {
            'snapshot_date': snapshot_date,
            'n_listings': len(group_df['id'].unique()),
            
            'n_price_valid': len(valid_price),
            'median_price_cad': valid_price['price'].median() if not valid_price.empty else np.nan,
            'price_q1_cad': valid_price['price'].quantile(0.25) if not valid_price.empty else np.nan,
            'price_q3_cad': valid_price['price'].quantile(0.75) if not valid_price.empty else np.nan,
            
            'n_room_type_valid': len(valid_room),
            'entire_home_share': (len(valid_room[valid_room['room_type'] == 'Entire home/apt']) / len(valid_room)) if len(valid_room) > 0 else np.nan,
            
            'n_calendar_listings': group_df['availability_share_mean'].notna().sum(),
            'availability_share_mean': group_df['availability_share_mean'].mean(),
            'calendar_coverage_mean': group_df['calendar_coverage_mean'].mean(),
            
            'n_rating_valid': len(valid_rating),
            'median_rating': valid_rating['review_scores_rating'].median() if not valid_rating.empty else np.nan
        }
        return pd.Series(res)

    # 5. TẠO 3 BẢNG THEO YÊU CẦU
    
    # Bảng 1: kpi_snapshot.csv (Tổng toàn thành phố)
    kpi_snapshot = calculate_metrics(df).to_frame().T
    
    # Bảng 2: kpi_area.csv (Nhóm theo khu vực)
    kpi_area = df.groupby('neighbourhood_cleansed').apply(calculate_metrics).reset_index()
    
    # Bảng 3: kpi_room_type.csv (Nhóm theo loại phòng)
    kpi_room_type = df.groupby('room_type').apply(calculate_metrics).reset_index()
    # Chỉnh sửa cột cho bảng room_type (Thêm room_type_share, bỏ entire_home_share)
    total_valid_rooms = kpi_snapshot['n_room_type_valid'].iloc[0]
    kpi_room_type['room_type_share'] = kpi_room_type['n_listings'] / total_valid_rooms
    kpi_room_type.loc[kpi_room_type['room_type'] == 'Unknown', 'room_type_share'] = np.nan
    kpi_room_type = kpi_room_type.drop(columns=['entire_home_share'])

    # 6. LƯU KẾT QUẢ
    os.makedirs(output_dir, exist_ok=True)
    kpi_snapshot.to_csv(os.path.join(output_dir, 'kpi_snapshot.csv'), index=False)
    kpi_area.to_csv(os.path.join(output_dir, 'kpi_area.csv'), index=False)
    kpi_room_type.to_csv(os.path.join(output_dir, 'kpi_room_type.csv'), index=False)
    print(f"Đã tính toán xong KPI cho mốc {snapshot_date}")

# Khối lệnh chạy thử
if __name__ == "__main__":
    # Cấu hình đường dẫn chạy thử (Bạn cần thay đổi cho khớp với máy bạn)
    test_config = {
        'snapshot_date': '2025-09-11',
        'input_dir': '../data/processed/2025-09-11', # Đường dẫn lấy dữ liệu SẠCH
        'output_dir': '../reports/kpi_results/2025-09-11' # Đường dẫn lưu kết quả
    }
    # run(test_config) # Bỏ comment dòng này khi đã có dữ liệu sạch để test