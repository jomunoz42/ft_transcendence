

export function connectWebSocket(): WebSocket {
  const socket = new WebSocket("ws://localhost:8000/ws");

  socket.onopen = () => {
    console.log("WebSocket connected");
  };

  socket.onmessage = (event) => {
    console.log("WebSocket event:", event.data);
  };

  socket.onclose = () => {
    console.log("WebSocket disconnected");
  };

  return socket;
}
