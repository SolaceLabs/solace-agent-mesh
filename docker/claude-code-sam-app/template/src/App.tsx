function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center p-4 overflow-hidden">
      <div className="text-center relative">
        {/* Animated background circles */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-white/10 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-purple-300/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        </div>

        {/* Main content */}
        <div className="relative">
          {/* Spinning logo/icon */}
          <div className="mb-8 inline-block">
            <div className="relative w-24 h-24">
              <div className="absolute inset-0 bg-white/20 backdrop-blur-sm rounded-2xl animate-spin" style={{ animationDuration: '3s' }}></div>
              <div className="absolute inset-2 bg-white/30 backdrop-blur-sm rounded-xl animate-spin" style={{ animationDuration: '2s', animationDirection: 'reverse' }}></div>
              <div className="absolute inset-0 flex items-center justify-center text-4xl">
                🚀
              </div>
            </div>
          </div>

          {/* Animated text */}
          <h1 className="text-5xl font-bold text-white mb-4 animate-pulse">
            Building Your First App
          </h1>

          <div className="flex items-center justify-center gap-2 text-white/90 text-lg">
            <span className="inline-block animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
            <span className="inline-block animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
            <span className="inline-block animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
          </div>

          <p className="mt-6 text-white/80 text-sm max-w-md mx-auto">
            Start chatting with the App Agent to build your application
          </p>
        </div>
      </div>
    </div>
  )
}

export default App
