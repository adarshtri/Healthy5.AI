"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Integration {
    platform: string;
    token: string;
    name: string;
    model_source: string;
    allowed_agents?: string[];
}

interface User {
    username: string;
    role: string;
    profile_name?: string;
    integrations: Integration[];
}

interface ChatMessage {
    id: string;
    role: "user" | "agent";
    text: string;
}

export default function DashboardPage() {
    const router = useRouter();
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    // Profile Name Box
    const [isEditingName, setIsEditingName] = useState(false);
    const [profileNameInput, setProfileNameInput] = useState("");

    // Add integration form
    const [showAddBot, setShowAddBot] = useState(false);
    const [botToken, setBotToken] = useState("");
    const [botName, setBotName] = useState("");
    const [modelSource, setModelSource] = useState("cloud");
    const [platform, setPlatform] = useState("telegram");

    // Allowed agents
    const [allowedAgents, setAllowedAgents] = useState<string[]>(["general"]);
    const availableAgents = [
        { id: "general", name: "General Assistant", description: "General chat, routing, and answering health questions." },
        { id: "weight", name: "Weight Tracker", description: "Log, update, and track your body weight over time." },
        { id: "profile", name: "Profile Manager", description: "Background data entry for saving user preferences and facts." },
        { id: "remind", name: "Reminder Bot", description: "Create, manage, and delete recurring reminders or tasks." }
    ];

    const toggleAgent = (agentId: string) => {
        setAllowedAgents(prev =>
            prev.includes(agentId)
                ? prev.filter(a => a !== agentId)
                : [...prev, agentId]
        );
    };

    // Editing state
    const [editingIntegrationParam, setEditingIntegrationParam] = useState<{ platform: string, token: string } | null>(null);

    // Chat State
    const [activeChatToken, setActiveChatToken] = useState<string | null>(null);
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [currentMessage, setCurrentMessage] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [eventSource, setEventSource] = useState<EventSource | null>(null);

    // Lazy Loading State
    const [skip, setSkip] = useState(0);
    const [hasMoreMessages, setHasMoreMessages] = useState(true);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const chatContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetchProfile();
    }, []);

    const fetchProfile = async () => {
        const token = localStorage.getItem("access_token");
        if (!token) {
            router.push("/login");
            return;
        }

        try {
            const res = await fetch("http://localhost:8000/api/auth/me", {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (!res.ok) throw new Error("Unauthorized");

            const userData = await res.json();
            setUser(userData);
            setProfileNameInput(userData.profile_name || userData.username);
        } catch (err) {
            localStorage.removeItem("access_token");
            router.push("/login");
        } finally {
            setLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem("access_token");
        router.push("/login");
    };

    const handleUpdateProfileName = async () => {
        const token = localStorage.getItem("access_token");
        try {
            const res = await fetch("http://localhost:8000/api/users/profile-name", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    profile_name: profileNameInput
                })
            });

            if (res.ok) {
                setIsEditingName(false);
                fetchProfile(); // refresh
            }
        } catch (err) {
            console.error(err);
        }
    }

    const handleAddIntegration = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = localStorage.getItem("access_token");
        try {
            const res = await fetch("http://localhost:8000/api/users/integrations", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    platform,
                    token: botToken,
                    name: botName,
                    model_source: modelSource,
                    allowed_agents: allowedAgents
                })
            });

            if (res.ok) {
                setShowAddBot(false);
                setBotToken("");
                setBotName("");
                setAllowedAgents(["general"]);
                fetchProfile(); // Refresh list
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleDeleteIntegration = async (platform: string, token: string) => {
        if (!confirm("Are you sure you want to delete this integration?")) return;
        try {
            const authToken = localStorage.getItem("access_token");
            const res = await fetch(`http://localhost:8000/api/users/integrations/${platform}/${token}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${authToken}` }
            });
            if (res.ok) {
                fetchProfile();
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleUpdateIntegration = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!editingIntegrationParam) return;
        try {
            const authToken = localStorage.getItem("access_token");
            const res = await fetch(`http://localhost:8000/api/users/integrations/${editingIntegrationParam.platform}/${editingIntegrationParam.token}`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    name: botName,
                    model_source: modelSource,
                    allowed_agents: allowedAgents
                })
            });

            if (res.ok) {
                setEditingIntegrationParam(null);
                setBotToken("");
                setBotName("");
                setAllowedAgents(["general"]);
                setShowAddBot(false);
                fetchProfile();
            }
        } catch (err) {
            console.error(err);
        }
    };

    const fetchChatHistory = async (session: string, currentSkip: number) => {
        setIsLoadingHistory(true);
        try {
            const authToken = localStorage.getItem("access_token");
            const res = await fetch(`http://localhost:8000/api/chat/history/${session}?skip=${currentSkip}`, {
                headers: { Authorization: `Bearer ${authToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                const historicalMsgs = data.messages.map((m: any) => ({
                    id: m._id || Date.now().toString() + Math.random().toString(),
                    role: m.sender,
                    text: m.text
                }));

                if (historicalMsgs.length < 20) {
                    setHasMoreMessages(false);
                }

                setChatMessages(prev => {
                    // Prepend older messages
                    return [...historicalMsgs, ...prev];
                });

                // Maintain scroll position roughly
                if (chatContainerRef.current && currentSkip > 0) {
                    const scrollNode = chatContainerRef.current;
                    const previousHeight = scrollNode.scrollHeight;
                    setTimeout(() => {
                        scrollNode.scrollTop = scrollNode.scrollHeight - previousHeight;
                    }, 10);
                }

                setSkip(currentSkip + 20);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoadingHistory(false);
        }
    };

    const openChat = () => {
        setActiveChatToken("web_ui");
        setChatMessages([]);
        setSkip(0);
        setHasMoreMessages(true);

        const sessionId = user?.username || "default_session";
        fetchChatHistory(sessionId, 0);

        const es = new EventSource(`http://localhost:8000/api/chat/stream/${sessionId}`);

        es.addEventListener("message", (e) => {
            const data = JSON.parse(e.data);
            setChatMessages(prev => [...prev, { id: Date.now().toString(), role: "agent", text: data.text }]);
        });

        es.addEventListener("connected", () => {
            console.log("Chat SSE Connected");
        });

        es.onerror = () => {
            console.error("SSE Error occurred. Reconnecting...");
        };

        setEventSource(es);
    };

    const closeChat = () => {
        if (eventSource) {
            eventSource.close();
            setEventSource(null);
        }
        setActiveChatToken(null);
        setChatMessages([]);
        setSkip(0);
    };

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        if (e.currentTarget.scrollTop === 0 && hasMoreMessages && !isLoadingHistory) {
            const sessionId = user?.username || "default_session";
            fetchChatHistory(sessionId, skip);
        }
    };

    const sendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!currentMessage.trim() || !activeChatToken) return;

        const text = currentMessage;
        // Optimistic UI
        setChatMessages(prev => [...prev, { id: Date.now().toString(), role: "user", text }]);
        setCurrentMessage("");
        setIsSending(true);

        try {
            const authToken = localStorage.getItem("access_token");
            await fetch("http://localhost:8000/api/chat/message", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    integration_token: "web_ui",
                    text: text,
                    session_id: user?.username || "default_session"
                })
            });
        } catch (err) {
            console.error("Failed to send message", err);
        } finally {
            setIsSending(false);
        }
    };

    if (loading) {
        return <div className="min-h-screen bg-black text-white flex items-center justify-center">Loading...</div>;
    }

    return (
        <div className="min-h-screen bg-zinc-950 text-white p-8">
            <div className="max-w-4xl mx-auto">
                <header className="flex items-center justify-between mb-12">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
                            Dashboard
                        </h1>
                        <div className="mt-2 flex items-center gap-3">
                            {isEditingName ? (
                                <div className="flex items-center gap-2">
                                    <input
                                        value={profileNameInput}
                                        onChange={e => setProfileNameInput(e.target.value)}
                                        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm outline-none w-48 focus:border-indigo-500"
                                        autoFocus
                                    />
                                    <button onClick={handleUpdateProfileName} className="text-xs bg-indigo-600 hover:bg-indigo-500 px-2 py-1 rounded">Save</button>
                                    <button onClick={() => { setIsEditingName(false); setProfileNameInput(user?.profile_name || user?.username || "") }} className="text-xs bg-zinc-700 hover:bg-zinc-600 px-2 py-1 rounded">Cancel</button>
                                </div>
                            ) : (
                                <p className="text-zinc-400">
                                    Welcome back, <span className="text-white font-medium">{user?.profile_name || user?.username}</span>
                                    <button onClick={() => setIsEditingName(true)} className="ml-2 text-xs text-indigo-400 hover:text-indigo-300 underline">Edit Name</button>
                                    <span className="ml-3 px-2 py-0.5 bg-zinc-800 text-xs rounded-full uppercase tracking-wider">{user?.role}</span>
                                </p>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        {user?.role === "admin" && (
                            <Link
                                href="/admin"
                                className="px-4 py-2 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 rounded-lg text-sm font-medium transition-all shadow-lg"
                            >
                                Admin Dashboard
                            </Link>
                        )}
                        <button
                            onClick={handleLogout}
                            className="px-4 py-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-lg text-sm font-medium transition-colors"
                        >
                            Sign Out
                        </button>
                    </div>
                </header>

                <section className="space-y-6">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold">My Integrations</h2>
                        <button
                            onClick={() => {
                                setEditingIntegrationParam(null);
                                setBotToken("");
                                setBotName("");
                                setAllowedAgents(["general"]);
                                setShowAddBot(!showAddBot);
                            }}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition-colors shadow-lg"
                        >
                            {showAddBot || editingIntegrationParam ? "Cancel" : "+ Add Configuration"}
                        </button>
                    </div>

                    {(showAddBot || editingIntegrationParam) && (
                        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 mb-6 animate-in fade-in slide-in-from-top-4 shadow-xl">
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="font-medium text-lg text-white">
                                    {editingIntegrationParam ? "Edit Integration Settings" : "Add New Integration"}
                                </h3>
                                {editingIntegrationParam && (
                                    <button onClick={() => setEditingIntegrationParam(null)} className="text-sm text-zinc-400 hover:text-white">Cancel Edit</button>
                                )}
                            </div>
                            <form onSubmit={editingIntegrationParam ? handleUpdateIntegration : handleAddIntegration} className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                        <label className="text-xs text-zinc-400">Integration Name (e.g., Name1_Telegram)</label>
                                        <input required type="text" value={botName} onChange={e => setBotName(e.target.value)} placeholder="My Fitness Bot" className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none" />
                                    </div>
                                    <div className="space-y-1 opacity-50">
                                        <label className="text-xs text-zinc-400">Bot Token (Immutable)</label>
                                        <input required disabled={!!editingIntegrationParam} type="text" value={editingIntegrationParam ? editingIntegrationParam.token : botToken} onChange={e => setBotToken(e.target.value)} placeholder="12345:ABCDE..." className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono outline-none" />
                                    </div>
                                    <div className="space-y-1 opacity-50">
                                        <label className="text-xs text-zinc-400">Platform (Immutable)</label>
                                        <select disabled={!!editingIntegrationParam} value={editingIntegrationParam ? editingIntegrationParam.platform : platform} onChange={e => setPlatform(e.target.value)} className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm outline-none appearance-none">
                                            <option value="telegram">Telegram</option>
                                            <option value="whatsapp">WhatsApp</option>
                                        </select>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs text-zinc-400">Model Source</label>
                                        <select value={modelSource} onChange={e => setModelSource(e.target.value)} className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none appearance-none">
                                            <option value="cloud">Cloud (Groq)</option>
                                            <option value="local">Local (Ollama)</option>
                                        </select>
                                    </div>
                                    <div className="space-y-2 col-span-2 mt-2">
                                        <label className="text-xs text-zinc-400">Enabled Agents</label>
                                        <div className="flex flex-wrap gap-3">
                                            {availableAgents.map(ag => (
                                                <label key={ag.id} className="flex items-center gap-2 text-sm text-zinc-300">
                                                    <input
                                                        type="checkbox"
                                                        checked={allowedAgents.includes(ag.id)}
                                                        onChange={() => toggleAgent(ag.id)}
                                                        className="rounded border-zinc-700 bg-black text-indigo-500 focus:ring-indigo-500"
                                                    />
                                                    <span title={ag.description}>{ag.id}</span>
                                                </label>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                                <button type="submit" className="w-full mt-4 bg-white text-black py-2.5 rounded-lg text-sm font-semibold hover:bg-zinc-200 transition-colors">
                                    {editingIntegrationParam ? "Update Settings" : "Save & Sync Webhook"}
                                </button>
                            </form>
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {user?.integrations?.length === 0 ? (
                            <div className="col-span-full py-12 text-center text-zinc-500 border border-dashed border-zinc-800 rounded-2xl bg-zinc-900/50">
                                You haven't configured any integrations yet. Click the button above to add one.
                            </div>
                        ) : (
                            user?.integrations?.map((int, i) => (
                                <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 hover:border-indigo-500/50 transition-colors shadow-lg">
                                    <div className="flex items-start justify-between mb-3">
                                        <div>
                                            <h3 className="font-medium text-lg text-white">{int.name}</h3>
                                            <p className="text-xs text-zinc-400 font-mono mt-1 blur-[3px] hover:blur-none transition-all cursor-crosshair" title="Hover to reveal token">
                                                {int.token}
                                            </p>
                                        </div>
                                        <div className="flex flex-col items-end gap-2">
                                            <span className="px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-full text-[10px] uppercase font-bold tracking-wider text-zinc-300">
                                                {int.platform}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex items-center justify-between mt-4">
                                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                                            Webhook Synced • Model: {int.model_source === 'cloud' ? 'Groq' : 'Local'} • Enabled Agents: {(int.allowed_agents || ["general"]).join(", ")}
                                        </div>
                                        <div className="flex gap-2 opacity-100 transition-opacity">
                                            <button
                                                onClick={() => {
                                                    setEditingIntegrationParam({ platform: int.platform, token: int.token });
                                                    setBotName(int.name);
                                                    setModelSource(int.model_source || "cloud");
                                                    setAllowedAgents(int.allowed_agents || ["general"]);
                                                    setShowAddBot(true); // Open the form
                                                    window.scrollTo({ top: 0, behavior: 'smooth' });
                                                }}
                                                className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-[10px] uppercase font-bold tracking-wider"
                                            >
                                                Edit
                                            </button>
                                            <button
                                                onClick={() => handleDeleteIntegration(int.platform, int.token)}
                                                className="px-3 py-1 bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-900/50 rounded text-[10px] uppercase font-bold tracking-wider"
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </section>

                <section className="mt-12 space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
                    <h2 className="text-xl font-semibold">Supported Agents</h2>
                    <p className="text-sm text-zinc-400 mb-4">You can switch to any of these specialized agents directly from your chat using commands or by simply asking.</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {availableAgents.map(agent => (
                            <div key={agent.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 hover:border-indigo-500/30 transition-colors shadow-lg flex flex-col h-full">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-400 font-bold hidden">
                                        {agent.name.charAt(0)}
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-white">{agent.name}</h3>
                                        <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-400 px-2 py-0.5 bg-indigo-500/10 rounded-full mt-1 inline-block">
                                            {agent.id}
                                        </span>
                                    </div>
                                </div>
                                <p className="text-sm text-zinc-400 flex-grow mt-2">{agent.description}</p>
                            </div>
                        ))}
                    </div>
                </section>
            </div>

            {/* Global Floating Chat Button */}
            {!activeChatToken && (
                <button
                    onClick={openChat}
                    className="fixed bottom-8 right-8 p-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full shadow-2xl hover:scale-110 transition-all z-40 group flex items-center justify-center"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                    <span className="max-w-0 overflow-hidden group-hover:max-w-xs transition-all duration-300 ease-in-out whitespace-nowrap ml-0 group-hover:ml-2 font-medium">Test Agent</span>
                </button>
            )}

            {/* Chat Modal Overlay */}
            {activeChatToken && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-lg h-[600px] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                        {/* Chat Header */}
                        <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                <h3 className="font-semibold text-white">Agent Debug Chat</h3>
                            </div>
                            <button
                                onClick={closeChat}
                                className="text-zinc-400 hover:text-white transition-colors"
                            >
                                ✕
                            </button>
                        </div>

                        {/* Chat Messages Log */}
                        <div
                            ref={chatContainerRef}
                            onScroll={handleScroll}
                            className="flex-1 overflow-y-auto p-4 space-y-4 bg-zinc-950/50 relative"
                        >
                            {isLoadingHistory && (
                                <div className="text-center text-xs text-zinc-500 py-2 animate-pulse">
                                    Loading older messages...
                                </div>
                            )}
                            {chatMessages.length === 0 && !isLoadingHistory ? (
                                <div className="h-full flex flex-col items-center justify-center text-zinc-500 text-sm space-y-2">
                                    <svg className="w-8 h-8 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                                    <p>Start typing to test the agent.</p>
                                    <p className="text-xs opacity-75">Messages flow exactly like Telegram.</p>
                                </div>
                            ) : (
                                chatMessages.map(msg => (
                                    <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${msg.role === 'user'
                                            ? 'bg-indigo-600 text-white rounded-br-none'
                                            : 'bg-zinc-800 text-zinc-200 border border-zinc-700 rounded-bl-none'
                                            }`}>
                                            {msg.text}
                                        </div>
                                    </div>
                                ))
                            )}
                            {isSending && (
                                <div className="flex justify-end">
                                    <div className="px-4 py-2 text-xs text-zinc-500">Sending...</div>
                                </div>
                            )}
                        </div>

                        {/* Chat Input */}
                        <form onSubmit={sendMessage} className="p-3 border-t border-zinc-800 bg-zinc-900">
                            <div className="flex items-center gap-2">
                                <input
                                    type="text"
                                    value={currentMessage}
                                    onChange={e => setCurrentMessage(e.target.value)}
                                    placeholder="Message the agent..."
                                    className="flex-1 bg-black border border-zinc-800 rounded-full px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                                    autoFocus
                                />
                                <button
                                    type="submit"
                                    disabled={!currentMessage.trim()}
                                    className="p-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full disabled:opacity-50 transition-colors"
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
