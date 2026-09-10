import duckdb

#Note duckdb is not installed in the container, so install it locally inside ur terminal
# pip install duckdb

con = duckdb.connect()
con.sql("INSTALL httpfs; LOAD httpfs;")
con.sql("INSTALL iceberg; LOAD iceberg;")

con.sql("SET s3_endpoint='localhost:9000';")
con.sql("SET s3_access_key_id='admin';")
con.sql("SET s3_secret_access_key='password123';")
con.sql("SET s3_use_ssl=false;")
con.sql("SET s3_url_style='path';")

# Enable version guessing to let DuckDB find the latest Iceberg metadata version
con.sql("SET unsafe_enable_version_guessing = true;")

result = con.sql("""
    SELECT * 
    FROM iceberg_scan('s3://warehouse/lakehouse/customer_commands_batch')
    LIMIT 10
""").show()