import pandas as pd
import numpy as np
import os 
import argparse
def run(cfg):
    date=cfg["snapshot_date"]
    in_dir=cfg["input_dir"]
    out_dir=cfg["output_dir"]
    #Tao duong dan tro toi file listing.csv,calendar.csv
    lst_path = os.path.join(in_dir, 'listings_clean.csv')
    cal_path = os.path.join(in_dir, 'calendar_listing_summary.csv')
    #Neu file listing.csv k ton tai thi bao loi
    if not os.path.exists(lst_path):
        print(f"Lỗi: Không tìm thấy {lst_path}")
        return
    #low_memory=false de pandas co the doc nhieu kieu du lieu
    # drop_duplicates(subset=['id']): xoa cac dong trung id ( 1 dong = 1 can nha)
    df_lst = pd.read_csv(lst_path,low_memory = False).drop_duplicates(subset=['id'])
    if os.path.exists(cal_path):
        df_cal = pd.read_csv(cal_path, low_memory=False)
        df_cal['is_avail'] = df_cal['available'] == 't'
        #tinh cung luc gia tri trung binh cua is_avail(ra ti le trong) va dem so dong(ra do phu ngay quan sat duoc)
        cal_sum = df_cal.groupby('listing_id').agg(
            availability_share_mean=('is_avail', 'mean'),
            calendar_coverage_mean=('date', 'count')
        ).reset_index()
        df = df_lst.merge(cal_sum, left_on='id', right_on='listing_id', how='left')
    else:
        #ko có file thi tao cot rong
        df = df_lst.copy()
        df['availability_share_mean'] = np.nan
        df['calendar_coverage_mean'] = np.nan
    if "price" in df.columns and df["price"].dtype == object:
        #xoa $ va dau phay neu co de cho no tro thanh chuoi
        df["price"]=df["price"].replace(r'[\$,]', '', regex=True).astype(float)
    elif "price" not in df.columns: #chong loi 
        df["price"] = np.nan
    #neu gia tri la Nan thi bien thanh Unknown
    df['room_type'] = df.get('room_type', pd.Series([np.nan]*len(df))).fillna('Unknown')
    df['neighbourhood_cleansed'] = df.get('neighbourhood_cleansed', pd.Series([np.nan]*len(df))).fillna('Unknown')
    def calc_kpi(grp):
        # loc ra cac gia tri khong hop le cho tung kpi
        v_price = grp.dropna(subset=['price'])
        v_room = grp[grp['room_type'] != 'Unknown']
        v_rate = grp.dropna(subset=['review_scores_rating'])
        v_cal = grp.dropna(subset=['availability_share_mean'])
        res = {
            'snapshot_date': date,
            'n_listings': len(grp), # Đếm tổng số căn
            
            'n_price_valid': len(v_price),
            # Tính trung vị (median). Điều kiện 'if not v_price.empty' là để chống lỗi hệ thống sập khi vùng đó không có căn nào có giá.
            'median_price_cad': v_price['price'].median() if not v_price.empty else np.nan,
            'price_q1_cad': v_price['price'].quantile(0.25) if not v_price.empty else np.nan,
            'price_q3_cad': v_price['price'].quantile(0.75) if not v_price.empty else np.nan,
            
            'n_room_type_valid': len(v_room),
            # Đếm số căn Entire home chia cho tổng căn có loại phòng hợp lệ.
            'entire_home_share': (len(v_room[v_room['room_type'] == 'Entire home/apt']) / len(v_room)) if len(v_room) > 0 else np.nan,
            
            'n_calendar_listings': len(v_cal),
            'availability_share_mean': v_cal['availability_share_mean'].mean() if not v_cal.empty else np.nan,
            'calendar_coverage_mean': v_cal['calendar_coverage_mean'].mean() if not v_cal.empty else np.nan,
            
            'n_rating_valid': len(v_rate),
            'median_rating': v_rate['review_scores_rating'].median() if not v_rate.empty else np.nan
        }
        return pd.Series(res)
    #Bảng Tổng (snapshot): Gọi hàm trên toàn bộ data gốc
    kpi_snap = calc_kpi(df).to_frame().T
    
    #Bảng Area: Cắt data gốc ra theo từng khu vực, rồi cho từng mảnh chạy qua hàm calc_kpi
    kpi_area = df.groupby('neighbourhood_cleansed').apply(calc_kpi).reset_index()
    
    #Bảng Room: Cắt theo từng loại phòng.
    kpi_room = df.groupby('room_type').apply(calc_kpi).reset_index()
    
    #Tính thị phần (share) của từng loại phòng
    # Lấy tổng số phòng hợp lệ từ bảng Snapshot
    tot_v_room = kpi_snap['n_room_type_valid'].iloc[0] 
    kpi_room['room_type_share'] = kpi_room['n_listings'] / tot_v_room
    
    # Chỉnh đè nhóm Unknown thành NaN (rỗng) vì Unknown không được tính tỷ lệ share
    kpi_room.loc[kpi_room['room_type'] == 'Unknown', 'room_type_share'] = np.nan
    # Xóa cột entire_home_share trong bảng Room vì nó thừa thãi (nhóm Private Room làm gì có căn Entire home nào mà tính)
    kpi_room = kpi_room.drop(columns=['entire_home_share'])
    # Tạo thư mục nếu nó chưa tồn tại (exist_ok=True để nếu có rồi thì bỏ qua không báo lỗi)
    os.makedirs(out_dir, exist_ok=True)
    
    # Xuất ra file Excel định dạng CSV, index=False để bỏ đi cột số thứ tự 0,1,2,3... không cần thiết
    kpi_snap.to_csv(os.path.join(out_dir, f'kpi_snapshot_{date}.csv'), index=False)
    kpi_area.to_csv(os.path.join(out_dir, f'kpi_area_{date}.csv'), index=False)
    kpi_room.to_csv(os.path.join(out_dir, f'kpi_room_type_{date}.csv'), index=False)
    
    print(f"Đã xuất 3 file KPI cho mốc {date}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=str, default='all') 
    args = parser.parse_args()
    
    # Đóng gói các biến thành 1 dictionary rồi truyền cho hàm run() ở tít trên đầu.
    cfg = {
        'snapshot_date': args.date,
        'input_dir': f'../data/processed/{args.date}', 
        'output_dir': f'../reports/kpi_results/'
    }
    run(cfg)
