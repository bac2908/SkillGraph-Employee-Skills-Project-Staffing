# Phân bổ theo thời gian và gợi ý có xét dung lượng

Ngày thực hiện: **17/09/2026**. Phạm vi: bản local, BE + FE, không triển khai
production, không sửa dữ liệu graph hoặc tài khoản đang dùng.

## 1. Mục đích và cách hiểu

Allocation là tỷ lệ **dung lượng làm việc dự kiến** dành cho dự án, không phải
điểm nhân viên, mức hoàn thành, số giờ đã làm hoặc năng suất. Nhân viên 100%
không đương nhiên làm tốt hơn người 40%. AVAILABLE là trạng thái thủ công,
không phải kết quả tính dung lượng và cũng không phải cam kết có thể nhận việc.

Ví dụ: nhân viên có 60% ở dự án A trong tháng 10, 60% ở B trong tháng 11.
Trước đây hai tỷ lệ bị cộng thành 120%; hiện mỗi tháng chỉ chiếm 60%. Có thể
thêm 40% xuyên suốt hai tháng, nhưng thêm 41% phải bị backend từ chối.
Ngược lại, nếu A kết thúc đúng ngày B bắt đầu, ngày đó cả hai cùng hiệu lực.

## 2. Quy tắc đã triển khai

- `WORKS_ON` thêm `start_date`, `end_date`, lưu chuỗi ISO `YYYY-MM-DD`.
  Tính **cả ngày bắt đầu và kết thúc**, không tính theo giờ.
- Mốc hôm nay thống nhất **UTC+07** ở BE/FE, độc lập múi giờ máy. Chưa có cấu
  hình lịch từng quốc gia, tuần làm việc, ngày lễ hoặc nghỉ phép.
- Ngày trống/null: không giới hạn về phía đó. Quan hệ cũ không có cả hai ngày
  vẫn là không giới hạn; **không tự ý giải phóng phần đã phân bổ của dữ liệu cũ**.
- Tỷ lệ vẫn 1–100, ngày kết thúc không trước ngày bắt đầu. Muốn kết thúc công
  việc thì sửa ngày kết thúc; không nhập allocation = 0.
- Tại mọi ngày trong khoảng phân công mới, tổng allocation của cùng nhân viên
  không được vượt 100%. Dùng thuật toán cộng/trừ ở các mốc ngày, lấy tải cao nhất
  `O(n log n)`, không cộng tất cả các công việc có giao với khoảng rồi kết luận
  quá tải. Không duyệt từng ngày nên khoảng không giới hạn vẫn tính được.
- Khi sửa, bỏ cạnh hiện tại của cặp nhân viên–dự án ra khỏi phép tính, rồi tính
  bản thay thế; không cộng trùng bản cũ. Đọc danh sách mới sau bước lấy khóa
  nhân viên, kiểm tra, ghi quan hệ và ghi audit trong cùng write transaction.
- Dashboard, hồ sơ nhân viên và tổng ở bảng phân công chỉ tính quan hệ **đang
  hiệu lực hôm nay**. Phân tích skill-gap hôm nay cũng không lấy người chưa bắt
  đầu/đã kết thúc. Bảng vẫn giữ và phân biệt cả ba trạng thái thời gian.
- Trạng thái Project COMPLETED không tự xóa/giải phóng assignment. Quản lý phải
  xác định ngày kết thúc thật; không suy diễn từ một lần đổi trạng thái dự án.
- Audit lưu cả hai ngày trước/sau. No-op với ngày thiếu/null không tạo sự kiện
  giả. Từ chối vượt tải không tạo thay đổi quan hệ/audit.

Khóa cần được kiểm chứng trên đúng engine đang dùng. Thiết kế dựa trên cơ chế
write lock của Cypher, xem [tài liệu Neo4j về truy cập đồng thời](https://neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access/).
Đây **không phải bằng chứng CognoDB đã đạt kiểm thử race**. Writer đi vòng API,
import hoặc Cypher trực tiếp không được lớp kiểm tra của ứng dụng bảo vệ.

## 3. Gợi ý nhân sự đã thay đổi thế nào?

Trên dashboard/chi tiết dự án có biểu mẫu kế hoạch: từ ngày, đến ngày, tỷ lệ cần
phân bổ và checkbox chỉ người đủ dung lượng. Phải bấm **Áp dụng kế hoạch**;
phần mô tả bên dưới ghi rõ kế hoạch nào đang áp dụng.

1. Giữ điều kiện AVAILABLE, kỹ năng đủ cấp cho ít nhất một kỹ năng GAP/MISSING.
2. Nhân viên đã có quan hệ với dự án không xuất hiện trong danh sách thêm mới
   (kể cả quan hệ hết hạn); sửa tại tab Phân công để không ghi đè ngầm.
3. Đọc allocation theo lô cho các ứng viên, không gọi graph riêng từng người.
   `period_remaining_allocation = 100 - peak` trong toàn bộ kỳ.
4. `can_allocate` chỉ đúng khi dung lượng đủ cho tỷ lệ người quản lý yêu cầu.
   Bật bộ lọc thì loại các ứng viên chưa đủ; tắt bộ lọc thì vẫn hiển thị lý do.
5. Xếp nhóm đủ dung lượng trước; trong nhóm, ưu tiên số kỹ năng phù hợp, số
   cộng tác, tổng cấp độ kỹ năng phù hợp, rồi ID. Không cộng thành điểm hiệu suất.
6. Cộng tác chỉ tính quan hệ có khoảng giao nhau và đã bắt đầu không muộn hơn
   hôm nay, với thành viên được phân công xuyên suốt kỳ kế hoạch. Ngày thiếu
   vẫn theo quy tắc legacy không giới hạn, không phải bằng chứng nhân sự xác nhận.
7. Bấm **Kiểm tra phân bổ** truyền đúng ngày/tỷ lệ vào biểu mẫu. Người quản lý
   vẫn xác nhận; lúc lưu BE kiểm tra lại. Kết quả gợi ý không giữ chỗ dung lượng.

**Phân tích kỹ năng trong gợi ý là thận trọng:** chỉ người được phân công trọn
kỳ mới tính vào đội. Hai người thay ca nối tiếp có thể thực tế bao phủ kỹ năng
cả kỳ nhưng vẫn bị báo thiếu trong phép tính này. Không dùng gợi ý để cam kết
coverage liên tục; chưa triển khai mô phỏng kỹ năng theo từng mốc thay đội.
Skill-gap hiển thị ở biểu đồ riêng vẫn là snapshot hôm nay.

## 4. API và hợp đồng dữ liệu

Không thêm route ghi mới, không nới quyền. Các route dưới đều cần đăng nhập.

### Tạo/thay phân công

`PUT /api/projects/{project_id}/assignments/{employee_id}`

```json
{
  "role": "Backend Developer",
  "allocation": 40,
  "start_date": "2026-10-01",
  "end_date": "2026-11-30"
}
```

201 khi tạo, 200 khi sửa, 422 nếu dữ liệu không hợp lệ, 409 nếu quá tải,
503 nếu graph lỗi. `DELETE` vẫn gỡ hẳn quan hệ và ghi audit.
**PUT là thay thế:** bỏ cả hai trường ngày trong request sẽ trở về không giới
hạn, không phải giữ ngày cũ. FE mới luôn gửi cả hai trường (chuỗi hoặc null).
Không chạy FE cũ song song để chỉnh assignment có ngày.

`GET /api/projects/{project_id}/assignments` vẫn trả toàn bộ các phân công:

| Trường | Ý nghĩa |
| --- | --- |
| `start_date`, `end_date` | Ngày hiệu lực, null nếu không giới hạn |
| `allocation_as_of` | Ngày lịch UTC+07 dùng tính tổng hôm nay |
| `employee_total_allocation` | Tổng đang hiệu lực hôm nay trên mọi dự án |
| `employee_remaining_allocation` | 100 trừ tổng hôm nay |
| `period_peak_allocation` | Tổng cao nhất trong kỳ của assignment đang xem, gồm cả assignment này |
| `period_remaining_allocation` | 100 trừ tổng cao nhất đó; khác với giới hạn thay thế ở form |

Giới hạn ở form = 100 trừ tải cao nhất **ở các dự án khác** trong kỳ đang chọn.
Số liệu xấu có sẵn có thể cho phần còn lại âm trên API; không che thành dữ liệu
khỏe. Hệ thống không tự sửa dữ liệu legacy quá tải.

### Gợi ý theo kế hoạch

```text
GET /api/projects/PROJ001/recommendations?start_date=2026-10-01&end_date=2026-10-31&required_allocation=20&capacity_only=true
```

- Ngày phải gửi đủ cặp và đúng thứ tự. Không gửi ngày: mặc định hôm nay–hôm nay.
- API mặc định `required_allocation=1`, `capacity_only=false` để client cũ vẫn
  thấy ứng viên đủ kỹ năng nhưng thiếu dung lượng. Thứ tự đã đổi sang capacity-first.
- FE mặc định hôm nay–hôm nay, cần 20%, bộ lọc bật. Đây là một ngày cụ thể;
  muốn nhiều ngày phải chọn kế hoạch trước khi áp dụng.
- Response trả kế hoạch, và ở từng ứng viên: `period_peak_allocation`,
  `period_remaining_allocation`, `can_allocate`. Không trả 0 giả khi đọc tải lỗi.

## 5. Phân quyền

- Admin sửa phân công mọi dự án; Manager chỉ dự án được giao; Viewer chỉ xem.
- Các role đọc nghiệp vụ đều xem được kế hoạch/gợi ý theo quyền đọc hiện có.
- Manager không được xem nhật ký chỉ dành Admin. Actor lấy từ phiên đăng nhập,
  không lấy từ payload. CSRF, buộc đổi mật khẩu, khóa/thu hồi phiên không đổi.
- Employee không đồng nghĩa tài khoản User. Chưa làm nhân viên tự đánh giá/
  xác nhận kỹ năng hoặc tự xin nhận việc.

## 6. File liên quan

- `backend/app/core/allocation.py`: lịch UTC+07 và thuật toán tải cao nhất.
- `backend/app/schemas/relationships.py`, `candidate_recommendation.py`: validation/response.
- `backend/app/api/project_assignments.py`, `projects.py`: request phân công/gợi ý.
- `backend/app/repositories/project_assignment_repository.py`: khóa, đọc tải,
  transaction và đọc gộp ứng viên.
- `project_repository.py`, `dashboard_repository.py`, `candidate_repository.py`:
  lọc thời gian cho coverage/dashboard/cộng tác.
- `activity_repository.py`: allowlist ngày trong audit.
- `backend/app/services/relationship_service.py`, `skill_gap_service.py`,
  `candidate_recommendation_service.py`: phối hợp nghiệp vụ.
- `frontend/src/allocation.ts`, `hooks.ts`: tính trước giới hạn form và tổng hôm nay.
- `frontend/src/components/Relations.tsx`, `Analysis.tsx`, `Activity.tsx`,
  `ui.tsx`, `pages/Dashboard.tsx`, `pages/Details.tsx`: biểu mẫu/hiển thị.
- `backend/tests/test_allocation.py`, `frontend/tests/allocation.spec.ts`:
  regression mới; `frontend/tests/graph.spec.ts`: kịch bản nghiệm thu thật đã mở rộng.

## 7. Cài đặt, dữ liệu cũ và backup

Không thêm dependency, environment variable, label, constraint hoặc SQLite
migration. Khởi động BE/FE theo [bàn giao](handoff.md); cần cập nhật cả hai cùng
phiên bản. Không chạy seed hoặc xóa quan hệ để nâng cấp.

Thay đổi graph là additive: hai thuộc tính chuỗi tùy chọn. Chưa chạy câu lệnh
migration nào trên DB của người dùng. Chủ dự án cần rà soát phân công cũ và
đặt ngày thật qua UI, không tự bịa ngày để giải phóng capacity.

Backup logic hiện có giữ toàn bộ properties dạng scalar nên giữ được ngày;
test xác nhận checksum đổi khi ngày đổi. Trước áp dụng lên dữ liệu thật, làm
backup theo [quy trình graph + SQLite](backup-restore.md). Chưa chạy phục hồi
thật cho phiên bản này. Không hạ BE về bản cũ trên dữ liệu đã có ngày vì bản
cũ cộng toàn bộ allocation và PUT có thể không giữ đúng quy tắc thời gian.

## 8. Kiểm chứng và giới hạn

Các lệnh tại backend (environment kiểm thử process dùng endpoint loopback
không có graph; SQLite tài khoản test nằm riêng, không dùng tài khoản thật):

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
```

Tại frontend:

```powershell
npm run build
npm run format:check
npm test
npm run test:rbac
npm run test:auth-stack
```

Kết quả thực chạy 17/09/2026 (UTC+07), Windows, Python 3.12.10, Node 24.19.0,
Edge headless; base commit `0d307cd`, kèm thay đổi worktree chưa commit.
Dùng dependency đã cài, không tạo thêm venv hoặc cài package mới:

| Kiểm tra | Kết quả và phạm vi |
| --- | --- |
| Ruff `app tests scripts` | PASS |
| BE `pytest -m "not integration" -q` | **330 passed, 1 skipped, 9 deselected**, 75,02 giây; 34 test mới ở `test_allocation.py`; skip symlink không đủ quyền trên Windows, integration không chạy |
| FE mặc định | **52 passed**, 2,0 phút ở lần cuối; 5 test allocation mới; API mock chỉ trong test |
| FE–FastAPI RBAC | **10 passed**, 49,5 giây; auth/SQLite thật riêng, graph stub |
| FE–FastAPI auth-stack | **1 passed**, 10,3 giây; graph stub, không chạm tài khoản thật |
| Build + Prettier | PASS; JS 351,76 kB / gzip 108,62 kB; CSS 36,08 kB / gzip 7,96 kB |
| Kiểm tra source bàn giao | `scripts.handoff check` PASS, 165 file; kiểm tra giới hạn đường dẫn/nội dung và secret local, không phải audit bảo mật đầy đủ |
| Graph thật / rollback engine / race theo ngày | **Chưa chạy**; không được suy ra PASS từ mock |

Trong quá trình thêm test graph, build từng báo thiếu kiểu `start_date`/
`end_date` của fixture audit; đã bổ sung kiểu và chạy build lại đạt. Sau chỉnh
trình bày cuối (checkbox đúng kích thước, giải thích có thể mở rộng trên mobile),
đã chạy lại đủ 52 test FE và xem ảnh mobile. Test dashboard rỗng được sửa để
nhận diện cả URL có query kế hoạch, chạy riêng thêm đạt 1/1 (không tính là test
mới). Không dùng số liệu bản bàn giao 16/09 để chứng nhận thay đổi này.
Không commit/push hoặc xuất ZIP thay thế bản bàn giao cũ.

Đã có test thuật toán so với oracle duyệt từng ngày trên 200 bộ dữ liệu tổng
hợp có seed cố định; kiểm tra legacy, ngày trùng biên, năm nhuận, giới hạn
0001/9999, update loại cạnh cũ, đúng 100%, quá tải, audit, backup checksum,
validation HTTP, gợi ý capacity-first/bộ lọc và fail-closed khi graph lỗi.
UI kiểm tra ngày sai, đổi kỳ, ngày hết hạn, giữ dữ liệu khi lưu lỗi và bàn giao
kế hoạch. Đây là offline/mocked-graph, không chứng minh engine thật.

Đã bổ sung bước 10b cho [graph E2E](graph-e2e-acceptance.md): 100% ở hai kỳ
rời nhau, trùng ngày bị chặn, hai yêu cầu 60% cùng kỳ từ hai phiên và kiểm tra
audit; dọn đúng hai quan hệ test. **Chưa chạy graph thật hoặc load test.**

### Chưa triển khai, không được hiểu nhầm là đã có

- Một cạnh cho mỗi Employee–Project: chưa có nhiều đợt/lịch sử phân công độc
  lập cho cùng cặp. Thay ngày là thay kế hoạch của cạnh; audit giữ trước/sau,
  nhưng không phải bảng timesheet hoặc kho lịch sử nhân sự bất biến.
- Không tự động loại ngày nghỉ, ngày lễ, part-time, đào tạo/nội bộ. Mẫu số vẫn
  là 100% dung lượng dự kiến, chưa quy đổi sang giờ/tuần cá nhân.
- Chưa có bằng chứng/xác nhận/độ mới của kỹ năng hoặc module đánh giá hiệu suất.
  Không dùng allocation để tự động thưởng, phạt hoặc xếp loại nhân viên.
- Chưa phát hiện lost update khi hai quản lý sửa cùng một phân công: capacity
  được kiểm tra lại nhưng bản lưu sau vẫn thay bản trước; audit giữ các thay đổi.
- Chưa tối ưu toàn hệ thống: selector/form vẫn đọc các dự án và phân công như
  trước; gợi ý đọc tải theo lô nhưng chưa phân trang ứng viên. Chưa đo dữ liệu lớn.
- Số liệu gợi ý/FE là snapshot không khóa giữ chỗ; qua ngày hoặc có người khác
  sửa cần tải lại. Trạng thái/skill hiện tại không dự báo nghỉ phép hay thay đổi
  năng lực tương lai. Kiểm tra cuối cùng luôn ở transaction ghi BE.

Hướng tiếp theo **mới là đề xuất**: nghiệm thu graph thật trên instance riêng,
sau đó thiết kế lịch làm việc cá nhân và kỹ năng có bằng chứng trước khi cân
nhắc bất kỳ đánh giá hiệu suất nào.
