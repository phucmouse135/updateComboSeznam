# generate_sql_ddl.py

def generate_sql():
    # 1. Mapping Java Type -> SQL Type
    type_map = {
        "Long": "BIGINT",
        "String": "VARCHAR(255)",
        "Text": "TEXT",
        "Integer": "INT",
        "BigDecimal": "DECIMAL(19,4)",
        "Boolean": "BIT",
        "Timestamp": "DATETIME",
        "Date": "DATE",
        "Time": "TIME",
        "Double": "FLOAT"
    }

    # 2. Định nghĩa Schema (Danh sách bảng và cột)
    # Format: "TableName": [("col_name", "Type", "Constraint")]
    # Constraint: "PK", "NN" (Not Null), "UQ" (Unique), "" (None)
    tables = {
        "User": [
            ("id", "Long", "PK"), ("username", "String", "NN"), ("password_hash", "String", "NN"),
            ("email", "String", "NN"), ("phone_number", "String", ""), ("status", "Integer", "NN"),
            ("is_email_verified", "Boolean", ""), ("created_at", "Timestamp", "NN")
        ],
        "Customer": [
            ("id", "Long", "PK"), ("membership_level", "String", ""), ("loyalty_points", "Integer", "NN"),
            ("wallet_balance", "BigDecimal", "NN")
        ],
        "Staff": [
            ("id", "Long", "PK"), ("employee_code", "String", "NN"), ("department_id", "Long", ""),
            ("position", "String", ""), ("salary", "BigDecimal", ""), ("start_date", "Date", "")
        ],
        "Admin": [("id", "Long", "PK"), ("security_level", "Integer", "NN")],
        "InventoryStaff": [("id", "Long", "PK"), ("warehouse_zone", "String", "")],
        
        "Book": [
            ("id", "Long", "PK"), ("isbn", "String", "NN"), ("title", "String", "NN"), ("slug", "String", "NN"),
            ("price", "BigDecimal", "NN"), ("stock_quantity", "Integer", "NN"), ("status", "Integer", "NN"),
            ("publisher_id", "Long", "NN")
        ],
        "EBook": [("id", "Long", "PK"), ("file_size", "Double", ""), ("format", "String", ""), ("download_url", "String", "")],
        "PhysicalBook": [("id", "Long", "PK"), ("weight", "Double", ""), ("dimensions", "String", ""), ("cover_type", "String", "")],
        "AudioBook": [("id", "Long", "PK"), ("duration_minutes", "Integer", ""), ("narrator_name", "String", "")],
        
        "Order": [
            ("id", "Long", "PK"), ("user_id", "Long", "NN"), ("order_code", "String", "NN"),
            ("order_date", "Timestamp", "NN"), ("total_amount", "BigDecimal", "NN"),
            ("status", "Integer", "NN"), ("payment_status", "Integer", "NN")
        ],
        "OrderItem": [
            ("id", "Long", "PK"), ("order_id", "Long", "NN"), ("book_id", "Long", "NN"),
            ("quantity", "Integer", "NN"), ("unit_price", "BigDecimal", "NN"), ("total_price", "BigDecimal", "NN")
        ],
        
        "Cart": [("id", "Long", "PK"), ("user_id", "Long", "NN"), ("updated_at", "Timestamp", "")],
        "CartItem": [("cart_id", "Long", "PK"), ("book_id", "Long", "PK"), ("quantity", "Integer", "NN")], # Composite PK
        
        "Payment": [
            ("id", "Long", "PK"), ("order_id", "Long", "NN"), ("amount", "BigDecimal", "NN"),
            ("provider", "String", ""), ("transaction_ref", "String", ""), ("status", "String", "NN"),
            ("pay_date", "Timestamp", "")
        ],
        "Shipment": [
            ("id", "Long", "PK"), ("order_id", "Long", "NN"), ("tracking_number", "String", ""),
            ("status", "String", "NN"), ("shipped_date", "Timestamp", "")
        ],
        
        "Category": [("id", "Long", "PK"), ("name", "String", "NN"), ("parent_id", "Long", "")],
        "Author": [("id", "Long", "PK"), ("name", "String", "NN"), ("bio", "Text", "")],
        "Publisher": [("id", "Long", "PK"), ("name", "String", "NN"), ("contact_email", "String", "")],
        
        "Review": [
            ("id", "Long", "PK"), ("user_id", "Long", "NN"), ("book_id", "Long", "NN"),
            ("rating", "Integer", "NN"), ("comment", "Text", ""), ("created_at", "Timestamp", "NN")
        ],
        
        "Warehouse": [("id", "Long", "PK"), ("name", "String", "NN"), ("location", "String", "")],
        "StockLevel": [
            ("id", "Long", "PK"), ("warehouse_id", "Long", "NN"), ("book_id", "Long", "NN"),
            ("quantity", "Integer", "NN"), ("min_stock", "Integer", "")
        ],
        "Supplier": [("id", "Long", "PK"), ("name", "String", "NN"), ("email", "String", "")],
        "PurchaseOrder": [
            ("id", "Long", "PK"), ("supplier_id", "Long", "NN"), ("total_cost", "BigDecimal", "NN"),
            ("status", "String", "NN"), ("created_date", "Timestamp", "NN")
        ],
        
        # Junction Tables (Many-to-Many)
        "BookAuthor": [("book_id", "Long", "PK"), ("author_id", "Long", "PK")],
        "BookCategory": [("book_id", "Long", "PK"), ("category_id", "Long", "PK")],
        
        # Additional tables for robustness
        "UserSession": [("id", "String", "PK"), ("user_id", "Long", "NN"), ("token", "String", "NN"), ("expires_at", "Timestamp", "")],
        "Address": [("id", "Long", "PK"), ("user_id", "Long", "NN"), ("street", "String", ""), ("city", "String", "")],
        "Role": [("id", "Long", "PK"), ("name", "String", "NN")],
        "UserRole": [("user_id", "Long", "PK"), ("role_id", "Long", "PK")],
        "Permission": [("id", "Long", "PK"), ("code", "String", "NN")],
        "RolePermission": [("role_id", "Long", "PK"), ("permission_id", "Long", "PK")],
        "TrackingLog": [("id", "Long", "PK"), ("shipment_id", "Long", "NN"), ("location", "String", ""), ("timestamp", "Timestamp", "")]
    }

    # 3. Định nghĩa Foreign Keys (Table, Column, RefTable, RefColumn)
    foreign_keys = [
        ("Customer", "id", "User", "id"), # Inheritance
        ("Staff", "id", "User", "id"), # Inheritance
        ("Admin", "id", "Staff", "id"),
        ("InventoryStaff", "id", "Staff", "id"),
        
        ("Book", "publisher_id", "Publisher", "id"),
        ("EBook", "id", "Book", "id"),
        ("PhysicalBook", "id", "Book", "id"),
        ("AudioBook", "id", "Book", "id"),
        
        ("Order", "user_id", "User", "id"),
        ("OrderItem", "order_id", "Order", "id"),
        ("OrderItem", "book_id", "Book", "id"),
        
        ("Cart", "user_id", "User", "id"),
        ("CartItem", "cart_id", "Cart", "id"),
        ("CartItem", "book_id", "Book", "id"),
        
        ("Payment", "order_id", "Order", "id"),
        ("Shipment", "order_id", "Order", "id"),
        
        ("Category", "parent_id", "Category", "id"),
        ("Review", "user_id", "User", "id"),
        ("Review", "book_id", "Book", "id"),
        
        ("StockLevel", "warehouse_id", "Warehouse", "id"),
        ("StockLevel", "book_id", "Book", "id"),
        ("PurchaseOrder", "supplier_id", "Supplier", "id"),
        
        ("BookAuthor", "book_id", "Book", "id"),
        ("BookAuthor", "author_id", "Author", "id"),
        ("BookCategory", "book_id", "Book", "id"),
        ("BookCategory", "category_id", "Category", "id"),
        
        ("UserSession", "user_id", "User", "id"),
        ("Address", "user_id", "User", "id"),
        ("UserRole", "user_id", "User", "id"),
        ("UserRole", "role_id", "Role", "id"),
        ("RolePermission", "role_id", "Role", "id"),
        ("RolePermission", "permission_id", "Permission", "id"),
        ("TrackingLog", "shipment_id", "Shipment", "id")
    ]

    sql_statements = []

    # Generate CREATE TABLE
    for table_name, columns in tables.items():
        sql = f"CREATE TABLE {table_name} (\n"
        pk_cols = []
        col_defs = []
        
        for col_name, col_type, constraint in columns:
            sql_type = type_map.get(col_type, "VARCHAR(255)")
            line = f"  {col_name} {sql_type}"
            
            if "NN" in constraint:
                line += " NOT NULL"
            
            col_defs.append(line)
            
            if "PK" in constraint:
                pk_cols.append(col_name)
        
        sql += ",\n".join(col_defs)
        
        if pk_cols:
            sql += f",\n  PRIMARY KEY ({', '.join(pk_cols)})"
            
        sql += "\n);\n"
        sql_statements.append(sql)

    # Generate ALTER TABLE ADD FOREIGN KEY
    for table, col, ref_table, ref_col in foreign_keys:
        fk_name = f"FK_{table}_{ref_table}_{col}"
        sql = f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} FOREIGN KEY ({col}) REFERENCES {ref_table} ({ref_col});"
        sql_statements.append(sql)

    return "\n".join(sql_statements)

print(generate_sql())