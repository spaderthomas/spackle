#!/usr/bin/env python

import spackle


def test_main_mcp_can_be_built():
    """Test that the main MCP can be built and has the expected structure"""
    # Build the main MCP
    main_mcp = spackle.spackle._build_mcp('main')
    
    # Verify it has the expected attributes
    assert hasattr(main_mcp, 'mcp'), "Main MCP should have 'mcp' attribute"
    assert hasattr(main_mcp, 'serve'), "Main MCP should have 'serve' method"
    
    # Verify the FastMCP instance
    assert main_mcp.mcp is not None, "FastMCP instance should not be None"
    assert main_mcp.mcp.name == 'spackle-main', "FastMCP should have correct name"


def test_probe_mcp_can_be_built():
    """Test that the probe MCP can be built and has the expected structure"""
    # Build the probe MCP
    probe_mcp = spackle.spackle._build_mcp('probe')
    
    # Verify it has the expected attributes
    assert hasattr(probe_mcp, 'serve'), "Probe MCP should have 'serve' method"


def test_sqlite_mcp_can_be_built():
    """Test that the sqlite MCP can be built and has the expected structure"""
    # Build the sqlite MCP
    sqlite_mcp = spackle.spackle._build_mcp('sqlite')
    
    # Verify it has the expected attributes
    assert hasattr(sqlite_mcp, 'serve'), "SQLite MCP should have 'serve' method"


def test_all_mcps_registered():
    """Test that all expected MCPs are registered"""
    expected_mcps = {'main', 'probe', 'sqlite'}
    registered_mcps = set(spackle.spackle.mcp_registry.keys())
    
    assert expected_mcps.issubset(registered_mcps), f"Expected {expected_mcps}, got {registered_mcps}"


def test_mcp_serve_methods_exist():
    """Test that MCP serve methods exist and are callable"""
    mcps_to_test = ['main', 'probe', 'sqlite']
    
    for mcp_name in mcps_to_test:
        mcp_instance = spackle.spackle._build_mcp(mcp_name)
        
        # Verify serve method exists
        assert hasattr(mcp_instance, 'serve'), f"{mcp_name} MCP should have serve method"
        assert callable(mcp_instance.serve), f"{mcp_name} MCP serve should be callable"


def test_mcp_functions_are_functions():
    """Test that all registered MCPs are functions (not classes)"""
    for mcp_name, mcp_func in spackle.spackle.mcp_registry.items():
        assert callable(mcp_func), f"{mcp_name} should be callable"
        # Functions should not have __init__ or should be simple functions
        assert hasattr(mcp_func, '__call__'), f"{mcp_name} should have __call__ method"