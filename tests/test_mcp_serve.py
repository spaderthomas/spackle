#!/usr/bin/env python

import spackle


def test_mcp_serve_methods():
  """Test that MCP serve methods exist and are callable for function-based MCPs"""

  # Test all MCP serve methods
  mcps_to_test = ['main', 'probe', 'sqlite']

  for mcp_name in mcps_to_test:
    # Build the MCP instance (wrapper around the function)
    mcp_instance = spackle.spackle._build_mcp(mcp_name)

    # Verify serve method exists
    assert hasattr(mcp_instance, 'serve'), f'{mcp_name} MCP should have serve method'
    assert callable(mcp_instance.serve), f'{mcp_name} MCP serve should be callable'


def test_mcp_registry_contains_functions():
  """Test that the MCP registry contains functions, not classes"""
  mcps_to_test = ['main', 'probe', 'sqlite']

  for mcp_name in mcps_to_test:
    # Get the function from the registry
    mcp_func = spackle.spackle.mcp_registry[mcp_name]

    # Verify it's a function
    assert callable(mcp_func), f'{mcp_name} should be a callable function'
    assert hasattr(mcp_func, '__name__'), f'{mcp_name} should have __name__ attribute'
    assert not hasattr(mcp_func, '__bases__'), (
      f'{mcp_name} should not be a class (no __bases__)'
    )


def test_function_wrapper_behavior():
  """Test that function wrappers work correctly"""
  # Test main MCP specifically (has special FastMCP handling)
  main_wrapper = spackle.spackle._build_mcp('main')
  assert hasattr(main_wrapper, 'mcp'), "Main MCP wrapper should have 'mcp' attribute"
  assert main_wrapper.mcp is not None, 'Main MCP FastMCP instance should not be None'

  # Test non-main MCP (simpler wrapper)
  probe_wrapper = spackle.spackle._build_mcp('probe')
  assert hasattr(probe_wrapper, 'serve'), "Probe MCP wrapper should have 'serve' method"
