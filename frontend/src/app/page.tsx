import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-black text-white relative overflow-hidden">
      {/* Ambient background glows */}
      <div className="absolute top-1/4 left-1/4 w-[30rem] h-[30rem] bg-purple-900/40 rounded-full blur-[128px] pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-1/4 right-1/4 w-[30rem] h-[30rem] bg-blue-900/40 rounded-full blur-[128px] pointer-events-none mix-blend-screen" />

      <main className="relative z-10 flex flex-col items-center justify-center px-4 text-center">
        <div className="mb-4 inline-flex items-center rounded-full border border-zinc-800 bg-zinc-900/50 px-3 py-1 text-sm text-zinc-300 backdrop-blur-md">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
          Gateway Online
        </div>

        <h1 className="max-w-3xl text-5xl sm:text-7xl font-bold tracking-tighter mb-6 bg-gradient-to-br from-white via-zinc-200 to-zinc-500 bg-clip-text text-transparent">
          Welcome to Healthy5.AI
        </h1>

        <p className="max-w-xl text-lg sm:text-xl text-zinc-400 mb-10 leading-relaxed">
          Your personal health and lifestyle companion. Set up your intelligence agent and connect it seamlessly to Telegram.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto">
          <Link
            href="/login"
            className="group relative inline-flex items-center justify-center px-8 py-4 font-medium text-white transition-all duration-200 bg-white/10 border border-white/20 rounded-full hover:bg-white/20 hover:scale-105 active:scale-95 overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500 to-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10 blur-xl" />
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500 to-blue-500 opacity-0 group-hover:opacity-20 transition-opacity duration-300 -z-10" />
            Access Dashboard
            <svg
              className="w-5 h-5 ml-2 -mr-1 transition-transform duration-200 group-hover:translate-x-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>
      </main>
    </div>
  );
}
