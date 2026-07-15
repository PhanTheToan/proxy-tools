Xây dựng một **Reverse Proxy cục bộ kết hợp ánh xạ cổng (Local Reverse Proxy Mapping)**.

Thay vì hoạt động như một Forward Proxy thông thường (như Burp Suite, nơi client phải cấu hình cài đặt proxy để "nhìn thấy" traffic), công cụ này sẽ hoạt động như một **bộ mặt đại diện (Gateway)** cho target site ngay tại máy của bạn. Bạn gọi vào cổng local nào, nó sẽ đóng vai trò là client để đi "giao tiếp" với target site đó rồi mang kết quả nguyên vẹn về cho bạn.

Dưới đây là phân tích chi tiết về kiến trúc hoạt động, các thách thức kỹ thuật cốt lõi và cách hiện thực hóa ý tưởng này.

---

## 1. Mô hình hoạt động (Workflow)

Khi bạn cấu hình mapping: `localhost:33121` $\rightarrow$ `[https://example.com](https://example.com)`

```
[Client / Curl] 
       │
       ▼ (1) Request gửi tới http://localhost:33121/api/users
[Your Proxy Tool]
       │ 
       │ ── Mở gói tin, sửa 'Host' header từ 'localhost:33121' thành 'example.com'
       │ ── Giữ nguyên Path (/api/users), Method, Headers, Body
       ▼ 
(2) Forward Request tới https://example.com/api/users
       │
[Target Server (example.com)]
       │
       ▼ (3) Trả về Response (HTML, JSON, Set-Cookie...)
[Your Proxy Tool]
       │
       │ ── (Tùy chọn) Sửa đổi các link hoặc Cookie chứa 'example.com' thành 'localhost:33121'
       ▼ 
(4) Trả lại Response nguyên vẹn cho [Client / Curl]

```

---

## 2. Các bài toán kỹ thuật cốt lõi cần giải quyết

Để kết quả từ `localhost` hiển thị "giống hệt" và hoạt động mượt mà như trang gốc, công cụ proxy của bạn phải xử lý được 3 vấn đề sau:

### A. Đổi Header `Host` (Bắt buộc)

Các web server hiện đại (Nginx, Cloudflare, Apache) sử dụng khái niệm **Virtual Hosts**. Nếu bạn gửi một request tới IP của `example.com` nhưng trong HTTP Header vẫn để `Host: localhost:33121`, server sẽ từ chối xử lý (trả về lỗi 404 hoặc 403). Proxy của bạn phải ghi đè header này trước khi forward đi.

### B. Xử lý TLS/SSL (HTTPS)

* **Chiều đi (Proxy $\rightarrow$ Target):** Bản chất lệnh curl của bạn gọi tới proxy qua `http` (Cleartext), nhưng proxy khi làm việc với `[https://example.com](https://example.com)` bắt buộc phải thực hiện bước bắt tay TLS (TLS Handshake) với target server.
* **Chiều về (Target $\rightarrow$ Proxy $\rightarrow$ Client):** Proxy nhận dữ liệu đã giải mã từ HTTPS, sau đó đẩy ngược lại cho Curl qua HTTP thường.

### C. Ghi đè liên kết (Link Rewriting) & Cookie Domain (Nâng cao)

Đây là điểm mấu chốt để "mapping toàn bộ site". Nếu trang web `example.com` trả về một đoạn mã HTML chứa các liên kết tuyệt đối dạng:

```html
<a href="https://example.com/profile">Profile</a>
<script src="https://example.com/assets/js/main.js"></script>

```

Khi bạn duyệt qua `localhost`, nếu click vào link trên, trình duyệt sẽ nhảy thẳng ra ngoài internet (`example.com`) thay vì ở lại proxy.

* **Giải pháp:** Proxy cần có tính năng **Response Body Rewriting** — quét qua dữ liệu trả về và thay thế toàn bộ chuỗi `[https://example.com](https://example.com)` thành `http://localhost:33121` trước khi trả về cho client.
* Tương tự với Header `Set-Cookie`, cần xóa bỏ thuộc tính `Domain=example.com` hoặc sửa thành `Domain=localhost` để trình duyệt chịu lưu cookie.

---

## 3. Cách triển khai thực tế

Bạn có thể tự code (Python, Node.js, Go) hoặc tận dụng các công cụ có sẵn để dựng nhanh.

### Phương án 1: Tự viết bằng Node.js (Sử dụng `http-proxy`)

Node.js rất mạnh về xử lý stream và proxy. Thư viện `http-proxy-middleware` hoặc `http-proxy` giúp bạn hiện thực hóa việc này chỉ trong vài dòng code:

```javascript
const http = require('http');
const httpProxy = require('http-proxy');

const TARGET = 'https://example.com';
const PORT = 33121;

const proxy = httpProxy.createProxyServer({
    target: TARGET,
    changeOrigin: true, // Tự động đổi Host header theo target
    autoRewrite: true,  // Tự động sửa các redirect header (Location)
});

const server = http.createServer((req, res) => {
    // Xử lý xuyên suốt cho mọi route
    proxy.web(req, res, {}, (err) => {
        console.error('Proxy Error:', err);
        res.writeHead(502);
        res.end('Bad Gateway');
    });
});

server.listen(PORT, () => {
    console.log(`Proxy mapping: http://localhost:${PORT} -> ${TARGET}`);
});

```

### Phương án 2: Sử dụng Nginx (Cấu hình nhanh)

Nếu không muốn code, bạn có thể tạo một file cấu hình Nginx động hoặc dùng một docker container chạy Nginx làm proxy:

```nginx
server {
    listen 33121;
    server_name localhost;

    location / {
        proxy_pass https://example.com;
        proxy_set_header Host example.com;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Sửa đổi nội dung HTML trả về (Yêu cầu ngx_http_sub_module)
        sub_filter 'https://example.com' 'http://localhost:33121';
        sub_filter_once off;
    }
}

```

---

## 4. Ứng dụng thực tế của ý tưởng này

Ý tưởng này cực kỳ hữu ích trong các kịch bản:

1. **Phân tích và Pentest nâng cao:** Bạn có thể chèn thêm các đoạn script (XSS payload, Hook script như BeEF) vào trực tiếp Response trả về từ trang web thật thông qua tầng Proxy này để test phía client-side mà không cần sở hữu mã nguồn trang web.
2. **Đánh lừa ứng dụng (Phishing/Red Teaming):** Tạo ra các cổng Reverse Proxy động (giống mô hình của Evilginx) để bypass MFA bằng cách đứng giữa mapping traffic.
3. **Tích hợp công cụ tự động:** Giúp các công cụ quét tự động (vốn chỉ thích làm việc với môi trường HTTP/Localhost không có cơ chế chặn) có thể tương tác dễ dàng với một target phức tạp ở xa.

