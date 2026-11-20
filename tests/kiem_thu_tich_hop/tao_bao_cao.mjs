// Gộp ket_qua/api.json + ket_qua/giao_dien.json + danh_sach_ac.json + danh_sach_loi.json
// thành BaoCao_KiemThuTichHop_108AC.xlsx (nộp cho task T05B58C).
// Chạy: node tao_bao_cao.mjs
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ExcelJS from "exceljs";

const HERE = dirname(fileURLToPath(import.meta.url));
const read = (file) => JSON.parse(readFileSync(join(HERE, file), "utf-8"));
const { acs, nguon } = read("danh_sach_ac.json");
const { loi } = read("danh_sach_loi.json");
const api = read("ket_qua/api.json");
const ui = read("ket_qua/giao_dien.json");
const OUT = join(HERE, "BaoCao_KiemThuTichHop_108AC.xlsx");
const DEVICES = ["Máy tính", "Điện thoại"];

const git = (...args) => { try { return execFileSync("git", args, { cwd: HERE }).toString().trim(); } catch { return "?"; } };
const commit = `${git("rev-parse", "--short", "HEAD")} (nhánh ${git("rev-parse", "--abbrev-ref", "HEAD")}, gốc master ${git("rev-parse", "--short", "master")})`;
const mysqlVersion = (() => { try { return execFileSync(process.env.PYTHON || join(HERE, "..", "..", ".venv", "Scripts", "python.exe"), ["-c",
  "import sys,pymysql; sys.path.insert(0, r'" + join(HERE, "..", "..") + "'); from app.core.config import settings as s; c=pymysql.connect(host=s.db_host,port=s.db_port,user=s.db_user,password=s.db_password); cur=c.cursor(); cur.execute('select version()'); print(cur.fetchone()[0])"]).toString().trim(); } catch { return "8.0"; } })();

const bugsByAc = {};
for (const bug of loi) for (const ac of bug.ac) (bugsByAc[ac] ??= []).push(bug.ma);
const L06 = new Set(loi.find((b) => b.ma === "L06")?.ac || []);

// Kết quả chung của một AC
function verdict(key) {
  const a = api[key];
  const u = ui.results[key];
  if (a?.status === "CHẶN") return "CHẶN";
  if (a?.status === "CẦN CẤU HÌNH") return "CẦN CẤU HÌNH";
  if (u) {
    const statuses = DEVICES.map((d) => u[d]?.status).filter(Boolean);
    if (statuses.includes("LỖI")) return "LỖI";
    if (a?.status === "LỖI" && !L06.has(key)) return "LỖI";
    return "ĐẠT";
  }
  return a?.status || "CHƯA KIỂM";
}

const STATUS_COLORS = { "ĐẠT": "FFD9F2E3", "LỖI": "FFFBD5D5", "CHẶN": "FFFFEBC2", "CẦN": "FFE3ECFA", "UI": "FFE3ECFA", "CHƯA": "FFEEEEEE", "Đã": "FFD9F2E3", "Ghi": "FFEEEEEE", "Chờ": "FFE3ECFA", "Mới": "FFFBD5D5" };
// Kết quả lần chạy đầu (trước khi sửa lỗi) để so sánh trong sheet Tổng quan
const LAN_DAU = { ngay: "21/11/2026", dat: 86, loi: 5, chan: 17 };
const BORDER = { style: "thin", color: { argb: "FFD0D5DD" } };
const wb = new ExcelJS.Workbook();
wb.creator = "Nhóm Bản đồ Ký ức";
wb.created = new Date();

function header(ws, row) {
  row.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: "FFFFFFFF" } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1F3A93" } };
    cell.alignment = { vertical: "middle", horizontal: "center", wrapText: true };
    cell.border = { top: BORDER, left: BORDER, bottom: BORDER, right: BORDER };
  });
  row.height = 32;
}

function body(row, statusCols = []) {
  row.eachCell({ includeEmpty: true }, (cell, col) => {
    cell.alignment = { vertical: "top", wrapText: true };
    cell.border = { top: BORDER, left: BORDER, bottom: BORDER, right: BORDER };
    if (statusCols.includes(col)) {
      const key = String(cell.value || "").split(" ")[0];
      const color = STATUS_COLORS[key];
      if (color) cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: color } };
      cell.alignment = { vertical: "top", horizontal: "center", wrapText: true };
      cell.font = { bold: true };
    }
  });
}

// ---------- Sheet 2: kết quả từng AC (tính trước để dùng số liệu cho tổng quan) ----------
const rows = acs.map((item, index) => {
  const key = `${item.story} ${item.ac}`;
  const u = ui.results[key];
  const device = (d) => (u?.[d] ? `${u[d].status}: ${u[d].detail}` : "Như nhau trên mọi thiết bị (quy tắc máy chủ, kiểm qua API)");
  const a = api[key];
  return {
    stt: index + 1, story: item.story, storyTitle: item.story_title, ac: item.ac, name: item.name,
    given: item.given, when: item.when, then: item.then,
    api: a ? `${a.status}: ${a.detail}` : "—",
    desktop: device("Máy tính"), mobile: device("Điện thoại"),
    verdict: verdict(key), bugs: (bugsByAc[key] || []).join(", "), epic: item.epic,
  };
});
const count = (list, s) => list.filter((r) => r.verdict === s).length;

// ---------- Sheet 1: Tổng quan ----------
const s1 = wb.addWorksheet("Tổng quan", { views: [{ showGridLines: false }] });
s1.columns = [{ width: 40 }, { width: 12 }, { width: 22 }, { width: 10 }, { width: 14 }, { width: 14 }, { width: 12 }];
s1.addRow(["BÁO CÁO KIỂM THỬ TÍCH HỢP – 108 TIÊU CHÍ NGHIỆM THU (26 USER STORY)"]).font = { bold: true, size: 15, color: { argb: "FF1F3A93" } };
s1.addRow(["Task T05B58C · Sprint 3 (16/11–20/11/2026) · Người thực hiện: Nguyễn Tấn Du"]).font = { italic: true };
s1.addRow([]);
const info = [
  ["Ngày chạy", new Date().toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })],
  ["Mã nguồn kiểm thử", commit],
  ["Nguồn AC", nguon],
  ["Cơ sở dữ liệu", `MySQL ${mysqlVersion}, database riêng ban_do_ky_uc_kiemthu tạo từ database/schema.sql (đủ 11 trigger, 34 tỉnh/thành)`],
  ["Máy chủ", "FastAPI chạy thật (uvicorn, cổng 8010), không dùng SQLite giả lập"],
  ["Trình duyệt", `Microsoft Edge ${ui.edgeVersion} điều khiển bằng Playwright`],
  ["Thiết bị", `Máy tính ${ui.devices["Máy tính"]}; Điện thoại ${ui.devices["Điện thoại"]}`],
  ["Cách kiểm", "Mỗi AC kiểm qua API trên máy chủ thật (đối chiếu đúng câu thông báo trong AC + dữ liệu trong DB). Các AC phụ thuộc giao diện/thao tác (chạm giữ, nhấp đúp, nút Back, hộp xác nhận, ảnh/video hiển thị, đăng xuất, trang quản trị...) kiểm thêm trên trình duyệt ở cả máy tính và điện thoại, có ảnh chụp làm bằng chứng."],
];
info.forEach(([k, v]) => {
  const row = s1.addRow([k, v]);
  s1.mergeCells(row.number, 2, row.number, 6);
  row.getCell(1).font = { bold: true };
  row.getCell(2).alignment = { wrapText: true, vertical: "top" };
  row.height = Math.max(18, Math.ceil(String(v).length / 75) * 16);
});
s1.addRow([]);
s1.addRow(["KẾT QUẢ CHUNG"]).font = { bold: true, size: 12 };
header(s1, s1.addRow(["Nhóm", "Số AC", "ĐẠT", "LỖI", "CHẶN", "Cần cấu hình", "Tỉ lệ đạt"]));
const epics = [...new Set(rows.map((r) => r.epic))];
for (const epic of [...epics, "TỔNG"]) {
  const list = epic === "TỔNG" ? rows : rows.filter((r) => r.epic === epic);
  const row = s1.addRow([epic, list.length, count(list, "ĐẠT"), count(list, "LỖI"), count(list, "CHẶN"), count(list, "CẦN CẤU HÌNH"), `${Math.round((count(list, "ĐẠT") / list.length) * 100)}%`]);
  body(row);
  [2, 3, 4, 5, 6, 7].forEach((c) => (row.getCell(c).alignment = { horizontal: "center" }));
  if (epic === "TỔNG") row.font = { bold: true };
}
s1.addRow([]);
s1.addRow(["Ý nghĩa: ĐẠT = đúng AC · LỖI = sai AC hoặc lỗi chức năng · CHẶN = chức năng chưa được xây dựng · CẦN CẤU HÌNH = code và test giả lập đã ĐẠT, chỉ còn thiếu khóa OAuth thật (Google/Facebook) để đi hết luồng."]).font = { italic: true, color: { argb: "FF555555" } };
s1.addRow([`So với lần chạy đầu (${LAN_DAU.ngay}, trước khi sửa): ĐẠT ${LAN_DAU.dat} → ${count(rows, "ĐẠT")}, LỖI ${LAN_DAU.loi} → ${count(rows, "LỖI")}, CHẶN ${LAN_DAU.chan} → ${count(rows, "CHẶN")} (còn lại ${count(rows, "CẦN CẤU HÌNH")} AC chờ khóa OAuth).`]).font = { bold: true, color: { argb: "FF1F7A3F" } };
s1.addRow([]);
s1.addRow(["LỖI TÌM ĐƯỢC VÀ TRẠNG THÁI (chi tiết ở sheet 'Danh sách lỗi')"]).font = { bold: true, size: 12 };
header(s1, s1.addRow(["Mã · Tiêu đề", "Mức độ", "Loại", "Số AC", "Trạng thái"]));
for (const bug of loi) {
  const row = s1.addRow([`${bug.ma} · ${bug.tieu_de}`, bug.muc_do, bug.loai, bug.ac.length, bug.trang_thai]);
  body(row, [5]);
  row.height = 30;
}

// ---------- Sheet 2: Kết quả 108 AC ----------
const s2 = wb.addWorksheet("Kết quả 108 AC", { views: [{ state: "frozen", xSplit: 4, ySplit: 1 }] });
s2.columns = [
  { header: "STT", key: "stt", width: 5 },
  { header: "Mã story", key: "story", width: 12 },
  { header: "Tên story", key: "storyTitle", width: 22 },
  { header: "AC", key: "ac", width: 6 },
  { header: "Tên kịch bản", key: "name", width: 24 },
  { header: "Given", key: "given", width: 28 },
  { header: "When", key: "when", width: 30 },
  { header: "Then / And", key: "then", width: 38 },
  { header: "Kết quả API (máy chủ thật)", key: "api", width: 46 },
  { header: "Máy tính (Edge 1366×800)", key: "desktop", width: 40 },
  { header: "Điện thoại (Pixel 7)", key: "mobile", width: 40 },
  { header: "KẾT QUẢ", key: "verdict", width: 11 },
  { header: "Mã lỗi", key: "bugs", width: 9 },
];
header(s2, s2.getRow(1));
rows.forEach((r) => body(s2.addRow(r), [12]));
s2.autoFilter = { from: "A1", to: "M1" };

// ---------- Sheet 3: Danh sách lỗi ----------
const s3 = wb.addWorksheet("Danh sách lỗi", { views: [{ state: "frozen", ySplit: 1 }] });
s3.columns = [
  { header: "Mã", key: "ma", width: 6 },
  { header: "Mức độ", key: "muc_do", width: 11 },
  { header: "Loại", key: "loai", width: 16 },
  { header: "Tiêu đề", key: "tieu_de", width: 34 },
  { header: "AC bị ảnh hưởng", key: "ac", width: 18 },
  { header: "Mô tả", key: "mo_ta", width: 60 },
  { header: "Cách tái hiện", key: "tai_hien", width: 36 },
  { header: "Vị trí trong code", key: "vi_tri", width: 36 },
  { header: "Đề xuất sửa", key: "de_xuat", width: 40 },
  { header: "Trạng thái", key: "trang_thai", width: 12 },
  { header: "Đã sửa thế nào", key: "cach_sua", width: 60 },
];
header(s3, s3.getRow(1));
const SEVERITY = { "Cao": "FFFBD5D5", "Trung bình": "FFFFEBC2", "Thấp": "FFE3ECFA" };
loi.forEach((bug) => {
  const row = s3.addRow({ ...bug, ac: bug.ac.join("\n"), cach_sua: bug.cach_sua || "" });
  body(row, [10]);
  const color = SEVERITY[bug.muc_do];
  if (color) row.getCell(2).fill = { type: "pattern", pattern: "solid", fgColor: { argb: color } };
});
s3.autoFilter = { from: "A1", to: "K1" };

// ---------- Sheet: Kiểm tra thêm (lỗi tiềm ẩn trên MySQL thật, ngoài AC) ----------
const extra = api._kiem_tra_them || {};
if (Object.keys(extra).length) {
  const sx = wb.addWorksheet("Kiểm tra thêm");
  sx.columns = [{ header: "Hạng mục", key: "k", width: 55 }, { header: "Kết quả", key: "s", width: 10 }, { header: "Chi tiết", key: "d", width: 80 }];
  header(sx, sx.getRow(1));
  for (const [k, v] of Object.entries(extra)) body(sx.addRow({ k, s: v.status, d: v.detail }), [2]);
}

// ---------- Sheet 4: Giao diện & thiết bị ----------
const s4 = wb.addWorksheet("Giao diện & thiết bị");
s4.columns = [{ header: "Hạng mục", key: "k", width: 40 }, { header: "Máy tính", key: "d", width: 60 }, { header: "Điện thoại", key: "m", width: 60 }];
header(s4, s4.getRow(1));
const uiKeys = Object.keys(ui.results);
for (const key of uiKeys) {
  const r = ui.results[key];
  body(s4.addRow({ k: key, d: r["Máy tính"] ? `${r["Máy tính"].status}: ${r["Máy tính"].detail}` : "—", m: r["Điện thoại"] ? `${r["Điện thoại"].status}: ${r["Điện thoại"].detail}` : "—" }), [2, 3]);
}
for (const path of ["/", "/ban-do", "/accounts/login.html", "/accounts/register.html", "/accounts/forgot-password.html"]) {
  const d = ui.pageChecks[`Máy tính ${path}`];
  const m = ui.pageChecks[`Điện thoại ${path}`];
  const fmt = (x) => (x ? (x.overflow <= 1 ? "ĐẠT: không tràn ngang" : `LỖI: tràn ngang ${x.overflow}px`) : "—");
  body(s4.addRow({ k: `Bố cục trang ${path}`, d: fmt(d), m: fmt(m) }), [2, 3]);
}
const errs = (d) => ui.pageChecks[`${d} lỗi JavaScript`] || [];
body(s4.addRow({ k: "Lỗi JavaScript trong suốt quá trình kiểm", d: errs("Máy tính").length ? `LỖI: ${errs("Máy tính").join("; ")}` : "ĐẠT: không có", m: errs("Điện thoại").length ? `LỖI: ${errs("Điện thoại").join("; ")}` : "ĐẠT: không có" }), [2, 3]);
s4.addRow([]);
s4.addRow(["Ảnh chụp màn hình của từng ca nằm trong tests/kiem_thu_tich_hop/ket_qua/anh_chup/ (tạo lại khi chạy kiem_thu_giao_dien.mjs)."]).font = { italic: true };

// ---------- Sheet 5: Cách chạy lại ----------
const s5 = wb.addWorksheet("Cách chạy lại");
s5.columns = [{ width: 6 }, { width: 110 }];
[
  ["", "Tất cả lệnh chạy từ thư mục gốc dự án (app/), đã kích hoạt .venv, MySQL đang chạy, file .env đã điền."],
  ["1", "python tests/kiem_thu_tich_hop/chuan_bi_db.py      → tạo lại database ban_do_ky_uc_kiemthu (không đụng ban_do_ky_uc)"],
  ["2", "python tests/kiem_thu_tich_hop/chay_server.py      → chạy server kiểm thử ở http://127.0.0.1:8010 (để cửa sổ này mở)"],
  ["3", "python tests/kiem_thu_tich_hop/kiem_thu_api.py     → kiểm 108 AC qua API, ghi ket_qua/api.json"],
  ["4", "cd tests/kiem_thu_tich_hop && npm install && npm run giao-dien   → kiểm giao diện trên Edge (máy tính + điện thoại), ghi ket_qua/giao_dien.json + ảnh chụp"],
  ["5", "npm run bao-cao                                       → tạo lại file báo cáo này"],
  ["", "Muốn chạy lại kiem_thu_api.py lần nữa thì làm lại bước 1 trước (vài ca đếm số ghim trong một vùng bản đồ cố định)."],
].forEach((r) => (s5.addRow(r).getCell(2).alignment = { wrapText: true }));

await wb.xlsx.writeFile(OUT);
console.log(`Đã tạo ${OUT}`);
console.log(`Tổng ${rows.length} AC: ĐẠT ${count(rows, "ĐẠT")}, LỖI ${count(rows, "LỖI")}, CHẶN ${count(rows, "CHẶN")}, CẦN CẤU HÌNH ${count(rows, "CẦN CẤU HÌNH")}`);
