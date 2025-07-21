# Thanks to https://github.com/hannesrudolph/sqlite-explorer-fastmcp-mcp-server
#
# Vendored instead of submoduled because this is just a base for a more featureful SQLite server


import os
import sqlite3
import sys

import spackle

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from fastmcp import FastMCP

@dataclass
class ColumnInfo:
  cid: int
  name: str
  type: str
  notnull: int
  dflt_value: Optional[str]
  pk: int


class SqliteConnection:
  def __init__(self, db_path: Path):
    self.db_path = db_path
    self.conn = None
    
  def __enter__(self):
    self.conn = sqlite3.connect(str(self.db_path))
    self.conn.row_factory = sqlite3.Row
    return self.conn
    
  def __exit__(self, exc_type, exc_val, exc_tb):
    if self.conn:
      self.conn.close()

@spackle.mcp(name = 'sqlite')
class SqliteServer:
  def __init__(self, db_path: Optional[str] = None):
    self.mcp = FastMCP("spackle-sqlite")
    
    self.db_path = Path(db_path)
    
    # Register tools
    self.mcp.tool(self.read_query)
    self.mcp.tool(self.list_tables)
    self.mcp.tool(self.describe_table)
  
  def serve(self):
    self.mcp.run()
  
  def read_query(
    self,
    query: str,
    params: Optional[List[Any]] = None,
    fetch_all: bool = True,
    row_limit: int = 1000
  ) -> List[Dict[str, Any]]:
    """Execute a query on the Messages database.
    
    Args:
      query: SELECT SQL query to execute
      params: Optional list of parameters for the query
      fetch_all: If True, fetches all results. If False, fetches one row.
      row_limit: Maximum number of rows to return (default 1000)
    
    Returns:
      List of dictionaries containing the query results
    """  
    # Clean and validate the query
    query = query.strip()
    
    # Remove trailing semicolon if present
    if query.endswith(';'):
      query = query[:-1].strip()
    
    # Check for multiple statements by looking for semicolons not inside quotes
    def contains_multiple_statements(sql: str) -> bool:
      in_single_quote = False
      in_double_quote = False
      for char in sql:
        if char == "'" and not in_double_quote:
          in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
          in_double_quote = not in_double_quote
        elif char == ';' and not in_single_quote and not in_double_quote:
          return True
      return False
    
    if contains_multiple_statements(query):
      raise ValueError("Multiple SQL statements are not allowed")
    
    # Validate query type (allowing common CTEs)
    query_lower = query.lower()
    if not any(query_lower.startswith(prefix) for prefix in ('select', 'with')):
      raise ValueError("Only SELECT queries (including WITH clauses) are allowed for safety")
    
    params = params or []
    
    with SqliteConnection(self.db_path) as conn:
      cursor = conn.cursor()
      
      try:
        # Only add LIMIT if query doesn't already have one
        if 'limit' not in query_lower:
          query = f"{query} LIMIT {row_limit}"
        
        cursor.execute(query, params)
        
        if fetch_all:
          results = cursor.fetchall()
        else:
          results = [cursor.fetchone()]
            
        return [dict(row) for row in results if row is not None]
        
      except sqlite3.Error as e:
        raise ValueError(f"Sqlite error: {str(e)}")
  
  def list_tables(self) -> List[str]:
    """List all tables in the Messages database.
    
    Returns:
      List of table names in the database
    """
    with SqliteConnection(self.db_path) as conn:
      cursor = conn.cursor()
      
      try:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        
        return [row['name'] for row in cursor.fetchall()]
        
      except sqlite3.Error as e:
        raise ValueError(f"SQLite error: {str(e)}")

  def describe_table(self, table_name: str) -> List[ColumnInfo]:
    """Get detailed information about a table's schema.
    
    Args:
      table_name: Name of the table to describe
      
    Returns:
      List of ColumnInfo objects containing column information:
      - cid: Column ID (int)
      - name: Column name (str)
      - type: Column data type (str)
      - notnull: Whether the column can contain NULL values (int: 0=can be null, 1=not null)
      - dflt_value: Default value for the column (str or None)
      - pk: Whether the column is part of the primary key (int: 0=no, 1=yes)
    """
    with SqlitConnection(self.db_path) as conn:
      cursor = conn.cursor()
      
      try:
        # Verify table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, [table_name])
        
        if not cursor.fetchone():
            raise ValueError(f"Table '{table_name}' does not exist")
        
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        return [ColumnInfo(
            cid=row['cid'],
            name=row['name'],
            type=row['type'],
            notnull=row['notnull'],
            dflt_value=row['dflt_value'],
            pk=row['pk']
        ) for row in columns]
        
      except sqlite3.Error as e:
        raise ValueError(f"SQLite error: {str(e)}")


def main():
  server = SqliteServer()
  server.serve()

if __name__ == "__main__":
  main()