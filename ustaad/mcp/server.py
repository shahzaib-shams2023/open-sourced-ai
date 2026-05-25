from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Local AI OS")

@mcp.tool()
def read_file(path: str):

    with open(path) as f:
        return f.read()

if __name__ == "__main__":
    mcp.run()
