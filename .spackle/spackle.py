import spackle

@spackle.tool
def foo(bar: str = None) -> spackle.McpResult:
  print(bar, file = sys.stderr)
  return spackle.McpResult(return_code = 0, stderr = '', stdout = '', response = bar)

spackle.configure(spackle.Config(
  blacklist = ['python', 'python3']
))
