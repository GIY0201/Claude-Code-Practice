import CesiumViewer from "./components/CesiumViewer";
import SimulationPanel from "./components/SimulationPanel";
import Dashboard from "./components/Dashboard";
import ChatPanel from "./components/ChatPanel";

function App() {
  return (
    <div className="h-screen w-screen flex flex-col bg-gray-900 text-white">
      <header className="h-12 flex items-center px-4 bg-gray-800 border-b border-gray-700 shrink-0 relative" style={{ zIndex: 100000 }}>
        <h1 className="text-lg font-bold">SkyMind — AI Drone ATC</h1>
      </header>
      <main className="flex-1 relative">
        <CesiumViewer />
        <SimulationPanel />
        <Dashboard />
        <ChatPanel />
      </main>
    </div>
  );
}

export default App;
