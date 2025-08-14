#!/usr/bin/env python

import spackle


def test_all_mcps_registered():
  """Test that all expected MCPs are registered"""
  expected_mcps = {'main', 'probe', 'sqlite'}
  registered_mcps = set(spackle.spackle.mcp_registry.keys())

  assert expected_mcps.issubset(registered_mcps), (
    f'Expected {expected_mcps}, got {registered_mcps}'
  )


def test_mcp_functions_are_functions():
  """Test that all registered MCPs are functions (not classes)"""
  for mcp_name, mcp_func in spackle.spackle.mcp_registry.items():
    assert callable(mcp_func), f'{mcp_name} should be callable'
    # Functions should not have __init__ or should be simple functions
    assert hasattr(mcp_func, '__call__'), f'{mcp_name} should have __call__ method'
