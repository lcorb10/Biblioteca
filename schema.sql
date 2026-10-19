-- =====================================================
-- Biblioteca Universitaria - MySQL 8.x (InnoDB)
-- Ejecutar completo en MySQL Workbench
-- =====================================================
DROP DATABASE IF EXISTS biblioteca;
CREATE DATABASE biblioteca CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE biblioteca;

CREATE TABLE configuracion (
    clave VARCHAR(50) PRIMARY KEY,
    valor VARCHAR(100) NOT NULL,
    descripcion VARCHAR(200)
);

CREATE TABLE personal (
    id_personal INT AUTO_INCREMENT PRIMARY KEY,
    login VARCHAR(50) NOT NULL UNIQUE,
    clave_hash VARCHAR(200) NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    rol ENUM('administrador','bibliotecario') NOT NULL DEFAULT 'bibliotecario'
);

CREATE TABLE editorial (
    id_editorial INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE autor (
    id_autor INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE
);

CREATE TABLE categoria (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE libro (
    isbn VARCHAR(20) PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    id_editorial INT NULL,
    anio SMALLINT NULL,
    descripcion TEXT NULL,
    FOREIGN KEY (id_editorial) REFERENCES editorial(id_editorial)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE libro_autor (
    isbn VARCHAR(20) NOT NULL,
    id_autor INT NOT NULL,
    PRIMARY KEY (isbn, id_autor),
    FOREIGN KEY (isbn) REFERENCES libro(isbn) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (id_autor) REFERENCES autor(id_autor) ON DELETE CASCADE
);

CREATE TABLE libro_categoria (
    isbn VARCHAR(20) NOT NULL,
    id_categoria INT NOT NULL,
    PRIMARY KEY (isbn, id_categoria),
    FOREIGN KEY (isbn) REFERENCES libro(isbn) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria) ON DELETE CASCADE
);

CREATE TABLE ejemplar (
    id_ejemplar INT AUTO_INCREMENT PRIMARY KEY,
    codigo_barras VARCHAR(30) NOT NULL UNIQUE,
    isbn VARCHAR(20) NOT NULL,
    ubicacion VARCHAR(80) NOT NULL,
    estado ENUM('disponible','prestado','perdido') NOT NULL DEFAULT 'disponible',
    FOREIGN KEY (isbn) REFERENCES libro(isbn) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE usuario (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    identificacion VARCHAR(20) NOT NULL UNIQUE,
    nombres VARCHAR(120) NOT NULL,
    correo VARCHAR(120) NOT NULL UNIQUE,
    rol ENUM('estudiante','docente') NOT NULL,
    carrera VARCHAR(100) NULL,
    estado ENUM('activo','bloqueado') NOT NULL DEFAULT 'activo'
);

-- Un préstamo nace como 'solicitado' (el usuario pide un libro/título).
-- El bibliotecario lo aprueba asignando un ejemplar -> 'activo'; o lo rechaza.
CREATE TABLE prestamo (
    id_prestamo INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    isbn VARCHAR(20) NOT NULL,
    id_ejemplar INT NULL,
    id_personal INT NULL,
    fecha_solicitud DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_prestamo DATE NULL,
    fecha_vencimiento DATE NULL,
    fecha_devolucion DATE NULL,
    estado ENUM('solicitado','rechazado','activo','devuelto') NOT NULL DEFAULT 'solicitado',
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario) ON DELETE RESTRICT,
    FOREIGN KEY (isbn) REFERENCES libro(isbn) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (id_ejemplar) REFERENCES ejemplar(id_ejemplar) ON DELETE RESTRICT,
    FOREIGN KEY (id_personal) REFERENCES personal(id_personal) ON DELETE SET NULL
);

CREATE TABLE devolucion (
    id_devolucion INT AUTO_INCREMENT PRIMARY KEY,
    id_prestamo INT NOT NULL UNIQUE,
    id_personal INT NULL,
    fecha_devolucion DATE NOT NULL,
    dias_retraso INT NOT NULL DEFAULT 0,
    multa DECIMAL(10,2) NOT NULL DEFAULT 0,
    condicion ENUM('bueno','dañado','páginas faltantes') NOT NULL DEFAULT 'bueno',
    observaciones VARCHAR(300) NULL,
    FOREIGN KEY (id_prestamo) REFERENCES prestamo(id_prestamo) ON DELETE RESTRICT,
    FOREIGN KEY (id_personal) REFERENCES personal(id_personal) ON DELETE SET NULL
);

CREATE INDEX idx_prestamo_estado ON prestamo(estado);
CREATE INDEX idx_ejemplar_estado ON ejemplar(estado);

-- =====================================================
-- DATOS BÁSICOS
-- =====================================================
INSERT INTO configuracion VALUES
('tarifa_multa_dia','2000','Multa en pesos por día de retraso'),
('dias_prestamo','7','Días de préstamo por defecto'),
('max_prestamos','3','Máximo de préstamos activos por usuario');

-- Admin inicial: login = admin / clave = admin123
INSERT INTO personal (login, clave_hash, nombres, rol) VALUES
('admin','6890118ed3e7ac16058d7a9d59219040$e855bbab90819645bc672469fefa03e7520ff2456cde4bf1aa47eff5ff86ec4d','Administrador General','administrador');

INSERT INTO editorial (nombre) VALUES ('Pearson'),('McGraw-Hill'),('Alfaguara'),('Sudamericana');
INSERT INTO autor (nombre) VALUES
('Abraham Silberschatz'),('Henry F. Korth'),('S. Sudarshan'),('Ramez Elmasri'),
('Shamkant Navathe'),('Gabriel García Márquez'),('Robert C. Martin');
INSERT INTO categoria (nombre) VALUES ('Bases de datos'),('Programación'),('Literatura'),('Ingeniería de software');

INSERT INTO libro (isbn, titulo, id_editorial, anio, descripcion) VALUES
('9780078022159','Database System Concepts',2,2019,'Texto clásico de fundamentos de bases de datos.'),
('9780133970777','Fundamentals of Database Systems',1,2015,'Modelado, SQL y diseño relacional.'),
('9780307474728','Cien años de soledad',4,1967,'Novela del realismo mágico.'),
('9780132350884','Clean Code',1,2008,'Guía de buenas prácticas de programación.');

INSERT INTO libro_autor VALUES
('9780078022159',1),('9780078022159',2),('9780078022159',3),
('9780133970777',4),('9780133970777',5),
('9780307474728',6),
('9780132350884',7);

INSERT INTO libro_categoria VALUES
('9780078022159',1),('9780133970777',1),('9780307474728',3),
('9780132350884',2),('9780132350884',4);

INSERT INTO ejemplar (codigo_barras, isbn, ubicacion, estado) VALUES
('EJ-0001','9780078022159','Sala 1 / Estante A2','disponible'),
('EJ-0002','9780078022159','Sala 1 / Estante A2','prestado'),
('EJ-0003','9780133970777','Sala 1 / Estante A3','disponible'),
('EJ-0004','9780307474728','Sala 2 / Estante B1','prestado'),
('EJ-0005','9780307474728','Sala 2 / Estante B1','disponible'),
('EJ-0006','9780132350884','Sala 1 / Estante C4','disponible'),
('EJ-0007','9780132350884','Sala 1 / Estante C4','perdido');

INSERT INTO usuario (codigo, identificacion, nombres, correo, rol, carrera, estado) VALUES
('U001','1001001001','Laura Pérez','laura@uni.edu.co','estudiante','Ingeniería de Sistemas','activo'),
('U002','1002002002','Carlos Gómez','carlos@uni.edu.co','estudiante','Ingeniería Industrial','activo'),
('U003','1003003003','María Rodríguez','maria@uni.edu.co','docente',NULL,'activo'),
('U004','1004004004','Pedro Díaz','pedro@uni.edu.co','estudiante','Derecho','bloqueado');

-- Un préstamo vencido (hace 12 días, vencía hace 5) y uno vigente, más una solicitud pendiente
INSERT INTO prestamo (id_usuario, isbn, id_ejemplar, id_personal, fecha_solicitud, fecha_prestamo, fecha_vencimiento, estado) VALUES
(1,'9780078022159',2,1, NOW() - INTERVAL 12 DAY, CURDATE() - INTERVAL 12 DAY, CURDATE() - INTERVAL 5 DAY,'activo'),
(2,'9780307474728',4,1, NOW() - INTERVAL 2 DAY,  CURDATE() - INTERVAL 2 DAY,  CURDATE() + INTERVAL 5 DAY,'activo');
INSERT INTO prestamo (id_usuario, isbn, fecha_solicitud, estado) VALUES
(3,'9780132350884', NOW(),'solicitado');
