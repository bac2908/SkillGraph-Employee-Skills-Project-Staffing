# Kiểm chứng hệ thống hiện có — graph, phục hồi và tải

Ngày kiểm tra: **19/09/2026**, Asia/Saigon. Mã nguồn đầu đợt: `8063f98`,
worktree sạch trước khi cập nhật tài liệu. Môi trường: Windows, Python 3.12.10,
Node.js 24.19.0, Microsoft Edge headless cho kiểm thử trình duyệt.

**Trạng thái: CHƯA NGHIỆM THU ĐẠT toàn hệ thống.** Đã kiểm tra điều kiện và
chạy hồi quy cô lập; chưa có kết quả FE → BE → graph thật, phục hồi graph thật
hoặc đo tải của đợt này. Không dùng số test ngoại tuyến để thay các bằng chứng đó.

## 1. Mục tiêu và phạm vi

- Tạo dữ liệu tổng hợp qua FE, đọc lại bằng API và driver graph độc lập.
- Kiểm tra allocation theo ngày, đúng 100%, vượt 100% và hai phiên ghi đồng thời.
- Kiểm tra quyền Manager/Viewer cả UI lẫn API trực tiếp.
- Backup graph và SQLite cùng đợt khi mọi bên ghi đã dừng; kiểm tra checksum,
  restore sang đích riêng, đối chiếu dữ liệu/quyền và chạy app phục hồi.
- Chứng minh phiên cũ không dùng được trong bản phục hồi, nguồn không bị sửa.
- Đo độ trễ, lỗi và tài nguyên với quy mô dữ liệu/mức đồng thời được ghi rõ.

Đợt này không triển khai production, không thêm phân hệ nghiệp vụ, không đổi
mật khẩu/tài khoản thật và không tự mở dịch vụ ra Internet.

## 2. Tiền kiểm thực tế

| Kiểm tra | Kết quả ngày 19/09 |
| --- | --- |
| `backend/.env.e2e` | Có file và user; URI, password chưa được điền |
| `backend/.env.restore` | Có file và user; URI, password chưa được điền |
| `scripts.graph_e2e preflight` | Exit code **1**: thiếu ba trường kết nối test đầy đủ; dừng trước kết nối |
| Bảo vệ Git | `.env.e2e`, `.env.restore`, `data/auth.sqlite3` được ignore |
| Listener trước kiểm thử | Không thấy listener 8000/5173/18001/5175 tại thời điểm kiểm tra; không chứng minh writer ở nơi khác đã dừng |
| Dung lượng ổ D | Khoảng 56,67 GiB trống tại thời điểm kiểm tra; không phải kích thước backup |

Chỉ báo trạng thái có/thiếu của cấu hình; không đưa giá trị URI, mật khẩu hoặc
nội dung kho tài khoản vào output/tài liệu. Không kết nối nguồn để thay thế đích
test bị thiếu. Không tự tạo cloud instance, không dùng Docker/DB khác để giả
lập kết quả nghiệm thu CognoDB.

## 3. Kiểm chứng đã chạy và cách chạy lại

Chạy tại `backend`; các biến sau chỉ là giá trị giả trong process kiểm thử,
không sửa `.env` và không phải credentials của instance thật:

```powershell
$env:COGNODB_URI='bolt://127.0.0.1:1'
$env:COGNODB_USER='offline-test'
$env:COGNODB_PASSWORD='offline-test-not-a-live-secret'
.\.venv\Scripts\python.exe -B -m pytest tests/test_graph_e2e.py tests/test_backup_restore.py tests/test_allocation.py tests/test_readiness.py -q
```

Dùng terminal test riêng và đóng terminal sau khi xong; không dùng các biến
giả này để khởi động ứng dụng thật. Các bài test dùng mock graph và SQLite tạm;
bài readiness có TCP peer cục bộ không trả lời để kiểm tra timeout.

Kết quả: **123 passed, 11,35 giây**. Bao gồm chặn nhầm nguồn/đích có dữ liệu,
checksum, restore SQLite/thu hồi phiên trên file tạm, bảo toàn ngày phân công,
kiểm tra tải cao nhất theo kỳ và readiness. Không có kết luận race trên CognoDB.

Chạy tại `frontend`:

```powershell
npm.cmd run build
npm.cmd run test:rbac
```

- TypeScript và Vite build: **PASS**; riêng Vite 1,90 giây.
- JS 355,48 kB (gzip 109,41 kB), CSS 37,21 kB (gzip 8,17 kB).
- RBAC: **10 passed, 40,7 giây**; FastAPI và SQLite thật ở môi trường tạm,
  graph mô phỏng. Kiểm tra Admin, Manager đúng/ngoài phạm vi, Viewer gọi API
  ghi trực tiếp, chưa đăng nhập, khóa/reset/đổi quyền thu hồi phiên và buộc đổi
  mật khẩu. Đây không phải nghiệm thu quyền cùng graph thật.
- Build là artifact cục bộ bị Git ignore, không phải deploy hoặc phép đo tải.
- Máy chủ test 5174/18000 đã dừng sau suite; không thấy listener khi kiểm tra
  lại. `git diff --check` đạt. Không chạy lại toàn bộ bộ test backend/frontend.

## 4. Điều kiện cần người vận hành cung cấp

1. Điền kết nối đích test riêng vào `.env.e2e` và `.env.restore` trên máy;
   không gửi mật khẩu vào chat/Git. Dùng các file `.example` làm hướng dẫn.
2. Xác nhận có một hay hai instance test, đích riêng thật sự và được phép chứa
   dữ liệu tổng hợp/bản sao nội bộ tương ứng; giữ độc quyền trong lúc chạy.
3. Thống nhất thời điểm dừng BE, seed/script và mọi bên ghi vào nguồn khi backup.
   Không cần tắt chính DB; CLI không thể tự xác nhận mọi writer bên ngoài.

Nếu chỉ có **một** instance test: E2E trước, kiểm tra bằng chứng và cleanup
đúng run-id; xác nhận đích trống lại rồi mới restore. Không chạy hai đợt đồng
thời, không xóa bản phục hồi để chạy lại E2E. Chưa tự điền cờ xác nhận vận hành
hoặc chạy cleanup khi chưa đủ điều kiện. Preflight phải chạy lại trước lần ghi.

Sau restore, đăng nhập app phục hồi trên cổng/SQLite riêng bằng kênh cục bộ an
toàn; không yêu cầu đưa mật khẩu thật vào chat và không reset tài khoản nguồn
chỉ để làm bài test. Báo cáo kỹ thuật restore chưa thay cho kiểm tra ứng dụng.

## 5. Kiểm thử tải — phần chưa thực hiện

Chưa có báo cáo benchmark hoặc runner benchmark riêng được kiểm chứng trong
đợt này. Ba vòng race trong E2E không phải load test. Không đặt số p95/RPS giả,
không chạy tải lên graph nguồn để bù cho việc thiếu cấu hình test.

Khi đích sẵn sàng, cần xác định dataset tổng hợp, cấu hình máy và ngưỡng chấp
nhận trước khi đo. Báo cáo tối thiểu phải có:

- Số Employee/Skill/Project, từng loại quan hệ và audit tại thời điểm chạy.
- Endpoint/tỷ lệ đọc–ghi, số phiên đồng thời, warm-up, thời lượng và timeout.
- Số request, throughput, p50/p95, timeout và lỗi ngoài dự kiến theo endpoint.
- Tách 401/403/409 chủ động thử khỏi lỗi ngoài dự kiến; không gộp thành PASS giả.
- CPU, RAM của BE, máy phát tải và tải nền ảnh hưởng phép đo. Tài nguyên graph
  cloud nếu không quan sát được phải ghi rõ, không suy ra từ CPU của máy BE.
- Kiểm tra dữ liệu/allocation/audit sau tải; lưu bằng chứng và xử lý dữ liệu
  tổng hợp theo đúng phạm vi. Không tự mở rộng thành tối ưu toàn hệ thống.

## 6. File, API và tài liệu liên quan

- `backend/scripts/graph_e2e.py`: preflight/run/cleanup và kiểm tra dữ liệu lưu thật.
- `frontend/tests/graph.spec.ts`, `frontend/playwright.graph.config.ts`:
  kịch bản FE/API, hai phiên ghi đồng thời và máy chủ test riêng.
- `backend/scripts/backup_restore.py`, `backup_support/`: backup/verify/restore.
- `backend/tests/test_allocation.py`, `test_graph_e2e.py`, `test_backup_restore.py`,
  `test_readiness.py`: hồi quy cô lập đã chạy.
- API nghiệp vụ `/api/employees`, `/api/skills`, `/api/projects`, assignments,
  requirements, skill-gap, recommendations; `/api/auth/*`, `/api/activity`
  và `/health/ready` theo quyền hiện hữu, không mở rộng quyền trong đợt này.
- [Quy trình E2E và tiêu chí đạt](graph-e2e-acceptance.md).
- [Quy trình backup/restore](backup-restore.md).
- [Ma trận ba role](rbac-acceptance.md).

Không có migration hoặc sửa code runtime trong đợt tiền kiểm này. Khi chạy
E2E thật, chỉ dùng migration đích qua runner sau khi kiểm tra schema và xác nhận.
Nguồn graph/auth không bị ghi bởi các lệnh đã chạy; chưa tạo bộ backup nguồn,
run-id E2E graph thật hoặc bản phục hồi graph trong đợt này. Kết luận toàn bộ
hạng mục vẫn là **CHỜ CẤU HÌNH VÀ ĐIỀU KIỆN VẬN HÀNH**, không phải hoàn thành.
