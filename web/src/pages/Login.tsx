

export default function Login() {
  const urlParams = new URLSearchParams(window.location.search);
  const error = urlParams.get('error');

  const handleLogin = () => {
    window.location.href = '/api/auth/discord';
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] flex flex-col items-center justify-center p-4">
      <div className="bg-[#151921] p-8 rounded-lg shadow-xl max-w-md w-full border border-gray-800 text-center">
        <h1 className="text-3xl font-bold text-white mb-2">PB HERO Bot</h1>
        <p className="text-gray-400 mb-8">Private Dashboard</p>
        
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 rounded p-3 mb-6">
            Authentication failed: {error}
          </div>
        )}

        <button
          onClick={handleLogin}
          className="w-full bg-[#5865F2] hover:bg-[#4752C4] text-white font-medium py-3 px-4 rounded transition-colors"
        >
          Login with Discord
        </button>
      </div>
    </div>
  );
}
