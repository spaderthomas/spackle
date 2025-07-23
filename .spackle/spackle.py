import spackle

@spackle.tool
def build() -> spackle.McpResult:
  return spackle.McpResult(
    return_code = 0,
    stderr = '',
    stdout = '',
    response = 'There is nothing to build in this project'
  )

@spackle.tool
def test() -> spackle.McpResult:
  spackle.wrap_subprocess([
    'uv', 'run', 'pytest'
  ])
