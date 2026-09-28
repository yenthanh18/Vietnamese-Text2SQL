INSERT INTO khoa (ma_khoa, ten_khoa) VALUES
('CNTT', 'Công nghệ thông tin'),
('KT', 'Kinh tế'),
('NN', 'Ngoại ngữ');

INSERT INTO nganh (ma_nganh, ten_nganh, ma_khoa) VALUES
('HTTT', 'Hệ thống thông tin', 'CNTT'),
('KTPM', 'Kỹ thuật phần mềm', 'CNTT'),
('QTKD', 'Quản trị kinh doanh', 'KT'),
('NNA', 'Ngôn ngữ Anh', 'NN');

INSERT INTO sinh_vien
(ma_sinh_vien, ho_ten, gioi_tinh, ngay_sinh, ma_nganh, khoa_hoc)
VALUES
('SV001', 'Nguyễn Minh Anh', 'Nữ', '2003-05-12', 'HTTT', 2021),
('SV002', 'Trần Quốc Bảo', 'Nam', '2002-11-08', 'HTTT', 2021),
('SV003', 'Lê Hoàng Nam', 'Nam', '2003-03-21', 'HTTT', 2021),
('SV004', 'Phạm Thu Hà', 'Nữ', '2004-07-15', 'KTPM', 2022),
('SV005', 'Võ Thành Công', 'Nam', '2003-09-10', 'KTPM', 2022),
('SV006', 'Đặng Ngọc Mai', 'Nữ', '2004-01-25', 'KTPM', 2022),
('SV007', 'Bùi Gia Hân', 'Nữ', '2003-06-18', 'QTKD', 2021),
('SV008', 'Nguyễn Đức Long', 'Nam', '2002-12-02', 'QTKD', 2021),
('SV009', 'Trần Khánh Linh', 'Nữ', '2004-04-30', 'NNA', 2022),
('SV010', 'Lê Minh Khang', 'Nam', '2003-08-14', 'NNA', 2022),
('SV011', 'Nguyễn Thảo Vy', 'Nữ', '2003-10-05', 'HTTT', 2021),
('SV012', 'Phan Quốc Huy', 'Nam', '2004-02-17', 'KTPM', 2022);

INSERT INTO mon_hoc
(ma_mon_hoc, ten_mon_hoc, so_tin_chi)
VALUES
('CT101', 'Cơ sở dữ liệu', 3),
('CT102', 'Lập trình Python', 3),
('CT103', 'Xử lý ngôn ngữ tự nhiên', 3),
('CT104', 'Học máy', 3),
('KT101', 'Quản trị học', 3),
('NN101', 'Tiếng Anh học thuật', 3);

INSERT INTO dang_ky
(ma_sinh_vien, ma_mon_hoc, hoc_ky, nam_hoc, diem)
VALUES
('SV001', 'CT101', 1, '2025-2026', 8.50),
('SV001', 'CT103', 1, '2025-2026', 9.00),
('SV001', 'CT104', 1, '2025-2026', 8.20),

('SV002', 'CT101', 1, '2025-2026', 7.50),
('SV002', 'CT103', 1, '2025-2026', 8.00),
('SV002', 'CT104', 1, '2025-2026', 7.80),

('SV003', 'CT101', 1, '2025-2026', 6.80),
('SV003', 'CT102', 1, '2025-2026', 7.20),
('SV003', 'CT103', 1, '2025-2026', 7.50),

('SV004', 'CT101', 1, '2025-2026', 8.80),
('SV004', 'CT102', 1, '2025-2026', 9.20),
('SV004', 'CT104', 1, '2025-2026', 8.70),

('SV005', 'CT101', 1, '2025-2026', 7.00),
('SV005', 'CT102', 1, '2025-2026', 7.80),
('SV005', 'CT104', 1, '2025-2026', 8.10),

('SV006', 'CT102', 1, '2025-2026', 8.60),
('SV006', 'CT103', 1, '2025-2026', 9.30),
('SV006', 'CT104', 1, '2025-2026', 9.00),

('SV007', 'KT101', 1, '2025-2026', 8.40),
('SV008', 'KT101', 1, '2025-2026', 7.60),

('SV009', 'NN101', 1, '2025-2026', 9.10),
('SV010', 'NN101', 1, '2025-2026', 8.00),

('SV011', 'CT101', 1, '2025-2026', 9.00),
('SV011', 'CT103', 1, '2025-2026', 9.50),
('SV011', 'CT104', 1, '2025-2026', 8.90),

('SV012', 'CT101', 1, '2025-2026', 7.90),
('SV012', 'CT102', 1, '2025-2026', 8.40),
('SV012', 'CT103', 1, '2025-2026', 8.70);