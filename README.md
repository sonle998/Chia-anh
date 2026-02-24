# Manga Splitter (Tách ảnh manga 2 trang)

Script `split_manga_spread.py` dùng để tách ảnh scan manga (2 trang trong 1 ảnh) thành ảnh trang đơn.

## Tính năng

- Tách ảnh theo thứ tự đọc manga mặc định **phải → trái**.
- Tự nhận diện nếp gấp gần giữa ảnh.
- Nhận diện thông minh ảnh 1 trang sẵn để **không tách nhầm**.
- Quét **toàn bộ ảnh trong folder và folder con**.
- Đánh số output theo từng folder: `001`, `002`, `003`, ...
- Tất cả kết quả được đặt trong thư mục gốc **`Tach anh`**.
- Mặc định xuất `png` để hạn chế giảm chất lượng.

## Yêu cầu

- Python 3.10+
- Pillow

Cài Pillow:

```bash
pip install pillow
```

## Cách chạy

### 1) Chạy cơ bản

```bash
python split_manga_spread.py "duong_dan_input"
```

Kết quả nằm trong thư mục `Tach anh/`.

### 2) Chỉ định nhiều input (file/folder)

```bash
python split_manga_spread.py folder_a image_01.jpg folder_b
```

### 3) Ghi vào thư mục con bên trong `Tach anh`

```bash
python split_manga_spread.py "du_lieu" -o "dot_1"
```

Output: `Tach anh/dot_1/...`

## Quy tắc đặt tên output

- Với mỗi folder nguồn, ảnh output được đánh số lại từ `001`.
- Ví dụ: `001.png`, `002.png`, `003.png`, ...

## Các tùy chọn chính

- `--split-x <int>`: ép vị trí cắt thủ công.
- `--gutter <int>`: bỏ vùng giữa gáy sách (pixel).
- `--ltr`: đổi thứ tự xuất sang trái → phải.
- `--search-ratio <float>`: phạm vi tìm nếp gấp quanh trung tâm.
- `--output-format {png,jpg,jpeg,webp,tif,tiff,bmp,same}`: định dạng output.
- `--jpeg-quality <1..100>`: chất lượng JPEG.
- `--no-skip-single`: luôn tách, tắt nhận diện ảnh 1 trang.
- `--min-aspect-ratio <float>`: ngưỡng tỉ lệ để nhận diện ảnh đơn.
- `--min-prominence <float>`: ngưỡng độ nổi nếp gấp.

## Ví dụ

### Tách toàn bộ ảnh trong thư mục (kèm folder con)

```bash
python split_manga_spread.py "./manga_raw"
```

### Xuất JPG chất lượng cao

```bash
python split_manga_spread.py "./manga_raw" --output-format jpg --jpeg-quality 100
```

### Luôn tách mọi ảnh, kể cả ảnh đơn

```bash
python split_manga_spread.py "./manga_raw" --no-skip-single
```

## Lưu ý

- Nếu dùng input là thư mục, script sẽ giữ cấu trúc thư mục tương ứng trong output.
- Nếu một ảnh được nhận diện là ảnh đơn, script sẽ giữ nguyên 1 trang thay vì tách đôi.
