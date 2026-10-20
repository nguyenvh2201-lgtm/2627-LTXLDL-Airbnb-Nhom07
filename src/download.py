"""Module download.py: Tải dữ liệu Inside Airbnb và kiểm tra tính toàn vẹn."""
"""python src/download.py """
import os
import gzip
import shutil
import logging
from typing import Dict, Any, List
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FILES_TO_DOWNLOAD = [
    ("data/listings.csv.gz", "listings.csv.gz"),
    ("data/calendar.csv.gz", "calendar.csv.gz"),
    ("data/reviews.csv.gz", "reviews.csv.gz"),
    ("visualisations/neighbourhoods.geojson", "neighbourhoods.geojson"),
]

def get_base_url(data_root: str, snapshot: str) -> str:
    """Xây dựng base url cho bản chụp Inside Airbnb."""
    data_root = data_root.strip("/")
    return f"https://data.insideairbnb.com/{data_root}/{snapshot}"

def download_file(url: str, dest_path: str, timeout: int = 60, overwrite: bool = True) -> bool:
    """Tải 1 tệp, xóa dữ liệu cũ khi overwrite=True để luôn tải về bản mới nhất."""
    # Nếu overwrite=True và file đã tồn tại, xóa file cũ trước khi tải
    if os.path.exists(dest_path):
        if overwrite:
            try:
                os.remove(dest_path)
                logger.info(f"Đã xoá file cũ để tải dữ liệu mới: {dest_path}")
            except Exception as e:
                logger.warning(f"Không thể xoá file cũ {dest_path}: {e}")
        elif os.path.getsize(dest_path) > 0:
            logger.info(f"File đã tồn tại (bỏ qua): {dest_path}")
            return True

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    temp_path = dest_path + ".tmp"
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except OSError:
            pass

    logger.info(f"Đang tải từ {url} -> {dest_path}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        with requests.get(url, stream=True, headers=headers, timeout=timeout) as response:
            if response.status_code == 200:
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                # Đảm bảo file đích không bị khóa trước khi di chuyển
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                shutil.move(temp_path, dest_path)
                logger.info(f"Tải thành công: {dest_path}")
                return True
            else:
                logger.warning(f"Không thể tải {url} - Status Code: {response.status_code}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
    except Exception as e:
        logger.error(f"Lỗi khi tải {url}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def verify_file(file_path: str, required_cols: List[str] = None) -> bool:
    """Kiểm tra tệp tồn tại, không rỗng và chứa các cột khóa cần thiết."""
    if not os.path.exists(file_path):
        return False
    if os.path.getsize(file_path) == 0:
        return False

    if required_cols and file_path.endswith(".csv.gz"):
        try:
            df_head = pd.read_csv(file_path, compression="gzip", nrows=5)
            for col in required_cols:
                if col not in df_head.columns:
                    logger.warning(f"File {file_path} thiếu cột bắt buộc: {col}")
                    return False
        except Exception as e:
            logger.error(f"Lỗi kiểm tra toàn vẹn {file_path}: {e}")
            return False
    return True

def run_download(config: Dict[str, Any], overwrite: bool = True) -> Dict[str, Any]:
    """Tải toàn bộ 4 mốc snapshot của thành phố được chỉ định trong config."""
    data_root = config.get("data_root")
    snapshots = config.get("snapshots", [])
    raw_dir = config.get("raw_dir", "data/raw")

    results = {}
    for snapshot in snapshots:
        snapshot_str = str(snapshot)
        logger.info(f"--- Bắt đầu xử lý snapshot: {snapshot_str} ---")
        snapshot_dir = os.path.join(raw_dir, snapshot_str)
        os.makedirs(snapshot_dir, exist_ok=True)
        base_url = get_base_url(data_root, snapshot_str)

        snapshot_status = {}
        for remote_rel, local_name in FILES_TO_DOWNLOAD:
            url = f"{base_url}/{remote_rel}"
            dest = os.path.join(snapshot_dir, local_name)
            success = download_file(url, dest, overwrite=overwrite)

            # Kiểm tra tính toàn vẹn
            req_cols = None
            if "listings" in local_name:
                req_cols = ["id", "price"]
            elif "calendar" in local_name:
                req_cols = ["listing_id", "date"]
            elif "reviews" in local_name:
                req_cols = ["id", "listing_id", "comments"]

            is_valid = verify_file(dest, req_cols)
            snapshot_status[local_name] = is_valid
        
        results[snapshot_str] = snapshot_status

    logger.info("Hoàn thành bước tải dữ liệu.")
    return results

if __name__ == "__main__":
    import yaml
    with open("configs/city.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    run_download(cfg, overwrite=True)
