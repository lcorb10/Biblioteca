# Modelos de la base de datos

## Diagrama Entidad–Relación (MER)

![MER](docs/MER.png)

Notación de Chen: entidades (rectángulos), relaciones (rombos, con su tipo encima), atributos (óvalos; subrayado = identificador) y cardinalidad (mín,máx) junto a cada entidad.
Fuente editable: [docs/fuentes/MER.html](docs/fuentes/MER.html) · versión Mermaid: [docs/mer.mmd](docs/mer.mmd).

## Diagrama Relacional

![Modelo relacional](docs/Modelo_Relacional.png)

Notación de patas de gallo; PK = clave primaria, FK = clave foránea, UK = única, (nulo) = acepta NULL.
Fuente editable: [docs/fuentes/Modelo_Relacional.html](docs/fuentes/Modelo_Relacional.html) · versión Mermaid: [docs/relacional.mmd](docs/relacional.mmd).

---

## Versión en texto del MER

```mermaid
erDiagram
    EDITORIAL ||--o{ LIBRO : publica
    LIBRO ||--o{ LIBRO_AUTOR : tiene
    AUTOR ||--o{ LIBRO_AUTOR : escribe
    LIBRO ||--o{ LIBRO_CATEGORIA : clasifica
    CATEGORIA ||--o{ LIBRO_CATEGORIA : agrupa
    LIBRO ||--o{ EJEMPLAR : "tiene copias"
    LIBRO ||--o{ PRESTAMO : "es solicitado en"
    USUARIO ||--o{ PRESTAMO : solicita
    EJEMPLAR |o--o{ PRESTAMO : "se asigna a"
    PERSONAL |o--o{ PRESTAMO : aprueba
    PRESTAMO ||--o| DEVOLUCION : "se cierra con"
    PERSONAL |o--o{ DEVOLUCION : registra

    LIBRO { string isbn PK
            string titulo
            int anio
            text descripcion }
    EJEMPLAR { int id_ejemplar PK
               string codigo_barras UK
               string ubicacion
               enum estado }
    USUARIO { int id_usuario PK
              string codigo UK
              string identificacion UK
              string nombres
              string correo
              enum rol
              string carrera
              enum estado }
    PRESTAMO { int id_prestamo PK
               datetime fecha_solicitud
               date fecha_prestamo
               date fecha_vencimiento
               date fecha_devolucion
               enum estado }
    DEVOLUCION { int id_devolucion PK
                 date fecha_devolucion
                 int dias_retraso
                 decimal multa
                 enum condicion
                 string observaciones }
```

# Modelo Relacional

- EDITORIAL(**id_editorial**, nombre)
- AUTOR(**id_autor**, nombre)
- CATEGORIA(**id_categoria**, nombre)
- LIBRO(**isbn**, titulo, #id_editorial, anio, descripcion)
- LIBRO_AUTOR(**#isbn, #id_autor**)
- LIBRO_CATEGORIA(**#isbn, #id_categoria**)
- EJEMPLAR(**id_ejemplar**, codigo_barras, #isbn, ubicacion, estado)
- USUARIO(**id_usuario**, codigo, identificacion, nombres, correo, rol, carrera, estado)
- PERSONAL(**id_personal**, login, clave_hash, nombres, rol)
- PRESTAMO(**id_prestamo**, #id_usuario, #isbn, #id_ejemplar, #id_personal, fecha_solicitud, fecha_prestamo, fecha_vencimiento, fecha_devolucion, estado)
- DEVOLUCION(**id_devolucion**, #id_prestamo, #id_personal, fecha_devolucion, dias_retraso, multa, condicion, observaciones)
- CONFIGURACION(**clave**, valor, descripcion)  — tarifa de multa por día, días de préstamo, máximo de préstamos

(**negrita** = PK, # = FK)
