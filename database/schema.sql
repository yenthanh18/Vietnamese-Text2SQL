DROP TABLE IF EXISTS dang_ky CASCADE;
DROP TABLE IF EXISTS mon_hoc CASCADE;
DROP TABLE IF EXISTS sinh_vien CASCADE;
DROP TABLE IF EXISTS nganh CASCADE;
DROP TABLE IF EXISTS khoa CASCADE;

CREATE TABLE khoa (
    ma_khoa VARCHAR(10) PRIMARY KEY,
    ten_khoa VARCHAR(100) NOT NULL
);

CREATE TABLE nganh (
    ma_nganh VARCHAR(10) PRIMARY KEY,
    ten_nganh VARCHAR(100) NOT NULL,
    ma_khoa VARCHAR(10) NOT NULL,
    FOREIGN KEY (ma_khoa) REFERENCES khoa(ma_khoa)
);

CREATE TABLE sinh_vien (
    ma_sinh_vien VARCHAR(15) PRIMARY KEY,
    ho_ten VARCHAR(100) NOT NULL,
    gioi_tinh VARCHAR(10),
    ngay_sinh DATE,
    ma_nganh VARCHAR(10) NOT NULL,
    khoa_hoc INTEGER,
    FOREIGN KEY (ma_nganh) REFERENCES nganh(ma_nganh)
);

CREATE TABLE mon_hoc (
    ma_mon_hoc VARCHAR(10) PRIMARY KEY,
    ten_mon_hoc VARCHAR(100) NOT NULL,
    so_tin_chi INTEGER NOT NULL
);

CREATE TABLE dang_ky (
    ma_sinh_vien VARCHAR(15) NOT NULL,
    ma_mon_hoc VARCHAR(10) NOT NULL,
    hoc_ky INTEGER NOT NULL,
    nam_hoc VARCHAR(10) NOT NULL,
    diem NUMERIC(4,2),
    PRIMARY KEY (ma_sinh_vien, ma_mon_hoc, hoc_ky, nam_hoc),
    FOREIGN KEY (ma_sinh_vien) REFERENCES sinh_vien(ma_sinh_vien),
    FOREIGN KEY (ma_mon_hoc) REFERENCES mon_hoc(ma_mon_hoc)
);