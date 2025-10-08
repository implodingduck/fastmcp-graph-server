import base64
from fastmcp import FastMCP
from mcp.types import TextContent, ImageContent

mcp = FastMCP("FastMCP Graph Server Example")

@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

@mcp.tool
def me():
    # Text content
    text = TextContent(type="text", text="Hello current user! Here is your profile picture:")

    # Image content (Base64 encoded)
    with open("app/sample_profile.png", "rb") as img_file:
        image_data = img_file.read()

    # Convert bytes to Base64
    base64_image = base64.b64encode(image_data).decode('utf-8')

    # Create ImageContent with just the base64 data
    image = ImageContent(type="image", data=base64_image, mimeType="image/png")

    text2 = TextContent(type="text", text="Thank you!")
    # Combine text and image into a response
    return [text, image, text2]

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)