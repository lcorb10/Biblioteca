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

-- =====================================================
-- DATOS DE EJEMPLO ADICIONALES (historial para los reportes)
-- =====================================================
INSERT INTO editorial (nombre) VALUES ('MIT Press'),('O''Reilly Media'),('Harper'),('Grove Press'),('Vintage Español');
INSERT INTO autor (nombre) VALUES ('Andrew S. Tanenbaum'),('Thomas H. Cormen'),('Isabel Allende'),('Jorge Luis Borges'),('Martin Kleppmann'),('Yuval Noah Harari');
INSERT INTO categoria (nombre) VALUES ('Redes'),('Algoritmos'),('Historia');

INSERT INTO libro (isbn, titulo, id_editorial, anio, descripcion) VALUES
('9780132126953','Computer Networks',1,2011,'Redes de computadores de la capa física a la de aplicación.'),
('9780262033848','Introduction to Algorithms',5,2009,'Referencia de algoritmos y estructuras de datos.'),
('9781449373320','Designing Data-Intensive Applications',6,2017,'Sistemas de datos confiables, escalables y mantenibles.'),
('9780062316097','Sapiens: A Brief History of Humankind',7,2015,'Breve historia de la humanidad.'),
('9780802130303','Ficciones',8,1983,'Cuentos fundamentales de Borges.'),
('9780525433477','La casa de los espíritus',9,2017,'Saga familiar de los Trueba.'),
('9780307389732','Love in the Time of Cholera',9,2003,'Una historia de amor que espera medio siglo.');
INSERT INTO libro_autor VALUES ('9780132126953',8),('9780262033848',9),('9781449373320',12),('9780062316097',13),('9780802130303',11),('9780525433477',10),('9780307389732',6);
INSERT INTO libro_categoria VALUES ('9780132126953',5),('9780262033848',6),('9780262033848',2),('9781449373320',1),('9781449373320',4),('9780062316097',7),('9780802130303',3),('9780525433477',3),('9780307389732',3);
INSERT INTO ejemplar (codigo_barras, isbn, ubicacion, estado) VALUES
('EJ-0008','9780132126953','Sala 1 / Estante D1','disponible'),
('EJ-0009','9780132126953','Sala 1 / Estante D1','disponible'),
('EJ-0010','9780262033848','Sala 1 / Estante D2','disponible'),
('EJ-0011','9780262033848','Sala 1 / Estante D2','disponible'),
('EJ-0012','9781449373320','Sala 1 / Estante A4','disponible'),
('EJ-0013','9781449373320','Sala 1 / Estante A4','disponible'),
('EJ-0014','9780062316097','Sala 3 / Estante H1','disponible'),
('EJ-0015','9780062316097','Sala 3 / Estante H1','disponible'),
('EJ-0016','9780802130303','Sala 2 / Estante B2','disponible'),
('EJ-0017','9780525433477','Sala 2 / Estante B3','disponible'),
('EJ-0018','9780525433477','Sala 2 / Estante B3','disponible'),
('EJ-0019','9780307389732','Sala 2 / Estante B1','disponible');

INSERT INTO usuario (codigo, identificacion, nombres, correo, rol, carrera, estado) VALUES
('U005','1005005005','Andrés Martínez','andres@uni.edu.co','estudiante','Ingeniería de Sistemas','activo'),
('U006','1006006006','Valentina Ruiz','valentina@uni.edu.co','estudiante','Medicina','activo'),
('U007','1007007007','Jorge Herrera','jorge@uni.edu.co','docente',NULL,'activo'),
('U008','1008008008','Camila Torres','camila@uni.edu.co','estudiante','Psicología','activo');

INSERT INTO prestamo (id_prestamo, id_usuario, isbn, id_ejemplar, id_personal, fecha_solicitud, fecha_prestamo, fecha_vencimiento, fecha_devolucion, estado) VALUES
(4,3,'9780525433477',17,1,NOW() - INTERVAL 21 DAY,CURDATE() - INTERVAL 20 DAY,CURDATE() - INTERVAL 6 DAY,CURDATE() - INTERVAL 6 DAY,'devuelto'),
(5,1,'9781449373320',13,1,NOW() - INTERVAL 145 DAY,CURDATE() - INTERVAL 144 DAY,CURDATE() - INTERVAL 137 DAY,CURDATE() - INTERVAL 134 DAY,'devuelto'),
(6,2,'9781449373320',13,1,NOW() - INTERVAL 115 DAY,CURDATE() - INTERVAL 114 DAY,CURDATE() - INTERVAL 107 DAY,CURDATE() - INTERVAL 107 DAY,'devuelto'),
(7,1,'9780078022159',1,1,NOW() - INTERVAL 155 DAY,CURDATE() - INTERVAL 154 DAY,CURDATE() - INTERVAL 140 DAY,CURDATE() - INTERVAL 140 DAY,'devuelto'),
(8,1,'9781449373320',13,1,NOW() - INTERVAL 126 DAY,CURDATE() - INTERVAL 125 DAY,CURDATE() - INTERVAL 115 DAY,CURDATE() - INTERVAL 115 DAY,'devuelto'),
(9,5,'9780062316097',15,1,NOW() - INTERVAL 158 DAY,CURDATE() - INTERVAL 157 DAY,CURDATE() - INTERVAL 147 DAY,CURDATE() - INTERVAL 147 DAY,'devuelto'),
(10,7,'9780307389732',19,1,NOW() - INTERVAL 50 DAY,CURDATE() - INTERVAL 49 DAY,CURDATE() - INTERVAL 39 DAY,CURDATE() - INTERVAL 39 DAY,'devuelto'),
(11,1,'9781449373320',13,1,NOW() - INTERVAL 109 DAY,CURDATE() - INTERVAL 108 DAY,CURDATE() - INTERVAL 101 DAY,CURDATE() - INTERVAL 101 DAY,'devuelto'),
(12,5,'9780062316097',14,1,NOW() - INTERVAL 127 DAY,CURDATE() - INTERVAL 126 DAY,CURDATE() - INTERVAL 119 DAY,CURDATE() - INTERVAL 118 DAY,'devuelto'),
(13,1,'9780132126953',8,1,NOW() - INTERVAL 138 DAY,CURDATE() - INTERVAL 137 DAY,CURDATE() - INTERVAL 127 DAY,CURDATE() - INTERVAL 127 DAY,'devuelto'),
(14,1,'9780307474728',5,1,NOW() - INTERVAL 33 DAY,CURDATE() - INTERVAL 32 DAY,CURDATE() - INTERVAL 25 DAY,CURDATE() - INTERVAL 24 DAY,'devuelto'),
(15,2,'9780062316097',15,1,NOW() - INTERVAL 42 DAY,CURDATE() - INTERVAL 41 DAY,CURDATE() - INTERVAL 31 DAY,CURDATE() - INTERVAL 31 DAY,'devuelto'),
(16,1,'9780133970777',3,1,NOW() - INTERVAL 128 DAY,CURDATE() - INTERVAL 127 DAY,CURDATE() - INTERVAL 117 DAY,CURDATE() - INTERVAL 117 DAY,'devuelto'),
(17,5,'9780062316097',14,1,NOW() - INTERVAL 89 DAY,CURDATE() - INTERVAL 88 DAY,CURDATE() - INTERVAL 78 DAY,CURDATE() - INTERVAL 78 DAY,'devuelto'),
(18,1,'9780132126953',9,1,NOW() - INTERVAL 125 DAY,CURDATE() - INTERVAL 124 DAY,CURDATE() - INTERVAL 117 DAY,CURDATE() - INTERVAL 117 DAY,'devuelto'),
(19,8,'9780132350884',7,1,NOW() - INTERVAL 42 DAY,CURDATE() - INTERVAL 41 DAY,CURDATE() - INTERVAL 34 DAY,CURDATE() - INTERVAL 34 DAY,'devuelto'),
(20,6,'9780078022159',2,1,NOW() - INTERVAL 61 DAY,CURDATE() - INTERVAL 60 DAY,CURDATE() - INTERVAL 46 DAY,CURDATE() - INTERVAL 45 DAY,'devuelto'),
(21,5,'9780132350884',6,1,NOW() - INTERVAL 12 DAY,CURDATE() - INTERVAL 11 DAY,CURDATE() - INTERVAL 1 DAY,CURDATE() - INTERVAL 1 DAY,'devuelto'),
(22,5,'9780262033848',11,1,NOW() - INTERVAL 160 DAY,CURDATE() - INTERVAL 159 DAY,CURDATE() - INTERVAL 152 DAY,CURDATE() - INTERVAL 152 DAY,'devuelto'),
(23,2,'9780262033848',10,1,NOW() - INTERVAL 25 DAY,CURDATE() - INTERVAL 24 DAY,CURDATE() - INTERVAL 17 DAY,CURDATE() - INTERVAL 17 DAY,'devuelto'),
(24,7,'9781449373320',13,1,NOW() - INTERVAL 144 DAY,CURDATE() - INTERVAL 143 DAY,CURDATE() - INTERVAL 133 DAY,CURDATE() - INTERVAL 131 DAY,'devuelto'),
(25,6,'9780802130303',16,1,NOW() - INTERVAL 76 DAY,CURDATE() - INTERVAL 75 DAY,CURDATE() - INTERVAL 61 DAY,CURDATE() - INTERVAL 61 DAY,'devuelto'),
(26,1,'9780078022159',1,1,NOW() - INTERVAL 155 DAY,CURDATE() - INTERVAL 154 DAY,CURDATE() - INTERVAL 144 DAY,CURDATE() - INTERVAL 143 DAY,'devuelto'),
(27,6,'9781449373320',13,1,NOW() - INTERVAL 127 DAY,CURDATE() - INTERVAL 126 DAY,CURDATE() - INTERVAL 119 DAY,CURDATE() - INTERVAL 117 DAY,'devuelto'),
(28,5,'9780307474728',4,1,NOW() - INTERVAL 107 DAY,CURDATE() - INTERVAL 106 DAY,CURDATE() - INTERVAL 99 DAY,CURDATE() - INTERVAL 99 DAY,'devuelto'),
(29,8,'9780132126953',8,1,NOW() - INTERVAL 34 DAY,CURDATE() - INTERVAL 33 DAY,CURDATE() - INTERVAL 19 DAY,CURDATE() - INTERVAL 18 DAY,'devuelto'),
(30,5,'9780307474728',5,1,NOW() - INTERVAL 33 DAY,CURDATE() - INTERVAL 32 DAY,CURDATE() - INTERVAL 25 DAY,CURDATE() - INTERVAL 25 DAY,'devuelto'),
(31,2,'9780132350884',6,1,NOW() - INTERVAL 21 DAY,CURDATE() - INTERVAL 20 DAY,CURDATE() - INTERVAL 13 DAY,CURDATE() - INTERVAL 13 DAY,'devuelto'),
(32,6,'9780062316097',14,1,NOW() - INTERVAL 18 DAY,CURDATE() - INTERVAL 17 DAY,CURDATE() - INTERVAL 10 DAY,CURDATE() - INTERVAL 10 DAY,'devuelto'),
(33,6,'9780132126953',8,1,NOW() - INTERVAL 141 DAY,CURDATE() - INTERVAL 140 DAY,CURDATE() - INTERVAL 133 DAY,CURDATE() - INTERVAL 133 DAY,'devuelto'),
(34,2,'9780307389732',19,1,NOW() - INTERVAL 166 DAY,CURDATE() - INTERVAL 165 DAY,CURDATE() - INTERVAL 158 DAY,CURDATE() - INTERVAL 158 DAY,'devuelto'),
(35,1,'9781449373320',13,1,NOW() - INTERVAL 47 DAY,CURDATE() - INTERVAL 46 DAY,CURDATE() - INTERVAL 39 DAY,CURDATE() - INTERVAL 39 DAY,'devuelto'),
(36,3,'9780132126953',8,1,NOW() - INTERVAL 125 DAY,CURDATE() - INTERVAL 124 DAY,CURDATE() - INTERVAL 117 DAY,CURDATE() - INTERVAL 115 DAY,'devuelto'),
(37,5,'9780307474728',5,1,NOW() - INTERVAL 71 DAY,CURDATE() - INTERVAL 70 DAY,CURDATE() - INTERVAL 63 DAY,CURDATE() - INTERVAL 63 DAY,'devuelto');
INSERT INTO devolucion (id_prestamo, id_personal, fecha_devolucion, dias_retraso, multa, condicion, observaciones) VALUES
(4,1,CURDATE() - INTERVAL 6 DAY,0,0,'bueno',NULL),
(5,1,CURDATE() - INTERVAL 134 DAY,3,6000,'bueno',NULL),
(6,1,CURDATE() - INTERVAL 107 DAY,0,0,'bueno',NULL),
(7,1,CURDATE() - INTERVAL 140 DAY,0,0,'dañado','Portada con rayones'),
(8,1,CURDATE() - INTERVAL 115 DAY,0,0,'bueno',NULL),
(9,1,CURDATE() - INTERVAL 147 DAY,0,0,'dañado','Portada con rayones'),
(10,1,CURDATE() - INTERVAL 39 DAY,0,0,'bueno',NULL),
(11,1,CURDATE() - INTERVAL 101 DAY,0,0,'dañado','Portada con rayones'),
(12,1,CURDATE() - INTERVAL 118 DAY,1,2000,'bueno',NULL),
(13,1,CURDATE() - INTERVAL 127 DAY,0,0,'bueno',NULL),
(14,1,CURDATE() - INTERVAL 24 DAY,1,2000,'bueno',NULL),
(15,1,CURDATE() - INTERVAL 31 DAY,0,0,'bueno',NULL),
(16,1,CURDATE() - INTERVAL 117 DAY,0,0,'bueno',NULL),
(17,1,CURDATE() - INTERVAL 78 DAY,0,0,'dañado','Portada con rayones'),
(18,1,CURDATE() - INTERVAL 117 DAY,0,0,'bueno',NULL),
(19,1,CURDATE() - INTERVAL 34 DAY,0,0,'bueno',NULL),
(20,1,CURDATE() - INTERVAL 45 DAY,1,2000,'bueno',NULL),
(21,1,CURDATE() - INTERVAL 1 DAY,0,0,'dañado','Portada con rayones'),
(22,1,CURDATE() - INTERVAL 152 DAY,0,0,'bueno',NULL),
(23,1,CURDATE() - INTERVAL 17 DAY,0,0,'bueno',NULL),
(24,1,CURDATE() - INTERVAL 131 DAY,2,4000,'dañado','Portada con rayones'),
(25,1,CURDATE() - INTERVAL 61 DAY,0,0,'dañado','Portada con rayones'),
(26,1,CURDATE() - INTERVAL 143 DAY,1,2000,'bueno',NULL),
(27,1,CURDATE() - INTERVAL 117 DAY,2,4000,'bueno',NULL),
(28,1,CURDATE() - INTERVAL 99 DAY,0,0,'bueno',NULL),
(29,1,CURDATE() - INTERVAL 18 DAY,1,2000,'bueno',NULL),
(30,1,CURDATE() - INTERVAL 25 DAY,0,0,'bueno',NULL),
(31,1,CURDATE() - INTERVAL 13 DAY,0,0,'bueno',NULL),
(32,1,CURDATE() - INTERVAL 10 DAY,0,0,'páginas faltantes','Faltan páginas del capítulo 3'),
(33,1,CURDATE() - INTERVAL 133 DAY,0,0,'bueno',NULL),
(34,1,CURDATE() - INTERVAL 158 DAY,0,0,'bueno',NULL),
(35,1,CURDATE() - INTERVAL 39 DAY,0,0,'bueno',NULL),
(36,1,CURDATE() - INTERVAL 115 DAY,2,4000,'bueno',NULL),
(37,1,CURDATE() - INTERVAL 63 DAY,0,0,'bueno',NULL);
