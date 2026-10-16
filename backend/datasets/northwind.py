"""Northwind dataset: the classic business tables, converted from the bundled dump.

The row data lives in ``data/northwind.json`` and is loaded once at import time.
"""

import json
import sqlite3
from pathlib import Path

_ID = "northwind"

_DATA = json.loads((Path(__file__).parent / "data" / "northwind.json").read_text(encoding="utf-8"))

_SQLITE_TYPES = {
    "integer": "INTEGER",
    "text": "TEXT",
    "decimal": "NUMERIC",
    "date": "TEXT",
    "boolean": "INTEGER",
}

TABLES = {
    "categories": {
        "description": "Product categories. One row per category.",
        "grain": "one row per category",
        "columns": ["CategoryID", "CategoryName", "Description"],
        "types": {"CategoryID": "integer", "CategoryName": "text", "Description": "text"},
        "keys": {"primary": ["CategoryID"], "foreign": []},
    },
    "customers": {
        "description": "Customer companies and their broad region.",
        "grain": "one row per customer company",
        "columns": ["CustomerID", "CompanyName", "City", "Region", "Country"],
        "types": {"CustomerID": "text", "CompanyName": "text", "City": "text", "Region": "text", "Country": "text"},
        "keys": {"primary": ["CustomerID"], "foreign": []},
    },
    "employees": {
        "description": "Employee role and work region.",
        "grain": "one row per employee",
        "columns": ["EmployeeID", "Title", "City", "Region", "Country"],
        "types": {"EmployeeID": "integer", "Title": "text", "City": "text", "Region": "text", "Country": "text"},
        "keys": {"primary": ["EmployeeID"], "foreign": []},
    },
    "employeeterritories": {
        "description": "Employee-to-territory assignments.",
        "grain": "one row per employee/territory assignment",
        "columns": ["EmployeeID", "TerritoryID"],
        "types": {"EmployeeID": "integer", "TerritoryID": "text"},
        "keys": {"primary": ["EmployeeID", "TerritoryID"], "foreign": ["EmployeeID -> employees.EmployeeID", "TerritoryID -> territories.TerritoryID"]},
    },
    "orderdetails": {
        "description": "Products and quantities on each order.",
        "grain": "one row per order/product line",
        "columns": ["OrderID", "ProductID", "UnitPrice", "Quantity", "Discount"],
        "types": {"OrderID": "integer", "ProductID": "integer", "UnitPrice": "decimal", "Quantity": "integer", "Discount": "decimal"},
        "keys": {"primary": ["OrderID", "ProductID"], "foreign": ["OrderID -> orders.OrderID", "ProductID -> products.ProductID"]},
    },
    "orders": {
        "description": "Order headers, dates, shipping region, and assigned employee.",
        "grain": "one row per order",
        "columns": ["OrderID", "CustomerID", "EmployeeID", "OrderDate", "RequiredDate", "ShippedDate", "ShipVia", "Freight", "ShipRegion", "ShipCountry"],
        "types": {"OrderID": "integer", "CustomerID": "text", "EmployeeID": "integer", "OrderDate": "date", "RequiredDate": "date", "ShippedDate": "date", "ShipVia": "integer", "Freight": "decimal", "ShipRegion": "text", "ShipCountry": "text"},
        "keys": {"primary": ["OrderID"], "foreign": ["CustomerID -> customers.CustomerID", "EmployeeID -> employees.EmployeeID", "ShipVia -> shippers.ShipperID"]},
    },
    "products": {
        "description": "Products, category, supplier, price, and inventory levels.",
        "grain": "one row per product",
        "columns": ["ProductID", "ProductName", "SupplierID", "CategoryID", "QuantityPerUnit", "UnitPrice", "UnitsInStock", "UnitsOnOrder", "ReorderLevel", "Discontinued"],
        "types": {"ProductID": "integer", "ProductName": "text", "SupplierID": "integer", "CategoryID": "integer", "QuantityPerUnit": "text", "UnitPrice": "decimal", "UnitsInStock": "integer", "UnitsOnOrder": "integer", "ReorderLevel": "integer", "Discontinued": "boolean"},
        "keys": {"primary": ["ProductID"], "foreign": ["SupplierID -> suppliers.SupplierID", "CategoryID -> categories.CategoryID"]},
    },
    "shippers": {
        "description": "Shipping companies.",
        "grain": "one row per shipper",
        "columns": ["ShipperID", "CompanyName"],
        "types": {"ShipperID": "integer", "CompanyName": "text"},
        "keys": {"primary": ["ShipperID"], "foreign": []},
    },
    "suppliers": {
        "description": "Supplier companies and broad location.",
        "grain": "one row per supplier company",
        "columns": ["SupplierID", "CompanyName", "City", "Region", "Country"],
        "types": {"SupplierID": "integer", "CompanyName": "text", "City": "text", "Region": "text", "Country": "text"},
        "keys": {"primary": ["SupplierID"], "foreign": []},
    },
    "territories": {
        "description": "Sales territories and their region IDs.",
        "grain": "one row per territory",
        "columns": ["TerritoryID", "TerritoryDescription", "RegionID"],
        "types": {"TerritoryID": "text", "TerritoryDescription": "text", "RegionID": "integer"},
        "keys": {"primary": ["TerritoryID"], "foreign": []},
    },
}

RELATIONSHIPS = [
    {"from_table": "products", "from_column": "CategoryID", "to_table": "categories", "to_column": "CategoryID", "cardinality": "many-to-one"},
    {"from_table": "products", "from_column": "SupplierID", "to_table": "suppliers", "to_column": "SupplierID", "cardinality": "many-to-one"},
    {"from_table": "orders", "from_column": "CustomerID", "to_table": "customers", "to_column": "CustomerID", "cardinality": "many-to-one"},
    {"from_table": "orders", "from_column": "EmployeeID", "to_table": "employees", "to_column": "EmployeeID", "cardinality": "many-to-one"},
    {"from_table": "orders", "from_column": "ShipVia", "to_table": "shippers", "to_column": "ShipperID", "cardinality": "many-to-one"},
    {"from_table": "orderdetails", "from_column": "OrderID", "to_table": "orders", "to_column": "OrderID", "cardinality": "many-to-one"},
    {"from_table": "orderdetails", "from_column": "ProductID", "to_table": "products", "to_column": "ProductID", "cardinality": "many-to-one"},
    {"from_table": "employeeterritories", "from_column": "EmployeeID", "to_table": "employees", "to_column": "EmployeeID", "cardinality": "many-to-one"},
    {"from_table": "employeeterritories", "from_column": "TerritoryID", "to_table": "territories", "to_column": "TerritoryID", "cardinality": "many-to-one"},
]


def ddl() -> str:
    """Build the CREATE TABLE script for this dataset."""
    statements = []
    for name, spec in TABLES.items():
        columns = ", ".join(f'"{column}" {_SQLITE_TYPES[spec["types"][column]]}' for column in spec["columns"])
        primary = spec["keys"]["primary"]
        if primary:
            columns += ", PRIMARY KEY (" + ", ".join(f'"{column}"' for column in primary) + ")"
        statements.append(f'CREATE TABLE "{name}" ({columns})')
    return ";\n".join(statements) + ";"


def seed(connection: sqlite3.Connection, size: str = "small") -> None:
    """Insert the converted rows. Deterministic: the same JSON every run."""
    for name, table in _DATA["tables"].items():
        columns = table["columns"]
        quoted = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        connection.executemany(
            f'INSERT INTO "{name}" ({quoted}) VALUES ({placeholders})',
            table["rows"],
        )
