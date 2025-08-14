#!/usr/bin/env python

import spackle


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
