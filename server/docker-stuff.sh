docker build -t fastmcp-graph-server .

docker stop fastmcp-graph-server
docker rm fastmcp-graph-server

docker run -d -p 8000:8000 --name fastmcp-graph-server fastmcp-graph-server
docker logs -f fastmcp-graph-server