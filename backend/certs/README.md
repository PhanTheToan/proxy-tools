# Internal CA certs

Đây là nơi thả các cert CA nội bộ (ví dụ CA của gateway UAT/corporate) để backend tin tưởng khi gọi HTTPS ra ngoài.

`backend/server.py` sẽ tự động load mọi file `.pem` / `.crt` trong thư mục này vào SSL trust store lúc khởi động (`build_ssl_context()`), cộng thêm vào trust store mặc định của hệ thống — không cần sửa code.

## Cách thêm cert

1. Xin/export file cert CA gốc (root/intermediate) ở định dạng PEM từ đội hạ tầng hoặc export từ trình duyệt/Keychain.
2. Copy file vào thư mục này, ví dụ: `backend/certs/my_internal_ca.pem`.
3. Restart backend để cert được load.

## Lưu ý

- Các file `*.pem` và `*.crt` trong thư mục này bị `.gitignore` — **không commit cert lên git**, vì đây là cấu hình riêng theo môi trường/máy.
- Chỉ file `README.md` này được track trong git để giữ thư mục tồn tại và có hướng dẫn.
