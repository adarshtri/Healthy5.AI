"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Integration {
    platform: string;
    token: string;
    name: string;
    model_source: string;
}

interface User {
    username: string;
    role: string;
    profile_name?: string;
    integrations: Integration[];
}

export default function AdminPage() {
    const router = useRouter();
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    // Admin user list
    const [allUsers, setAllUsers] = useState<User[]>([]);
    const [newUsername, setNewUsername] = useState("");
    const [newPassword, setNewPassword] = useState("");

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
            if (userData.role !== "admin") {
                router.push("/dashboard");
                return;
            }

            setUser(userData);
            fetchUsers(token);
            fetchSettings(token);
        } catch (err) {
            localStorage.removeItem("access_token");
            router.push("/login");
        } finally {
            setLoading(false);
        }
    };

    const fetchUsers = async (token: string) => {
        try {
            const res = await fetch("http://localhost:8000/api/users", {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                setAllUsers(await res.json());
            }
        } catch (err) {
            console.error(err);
        }
    };

    const [webhookUrl, setWebhookUrl] = useState("");
    const [journalBasePath, setJournalBasePath] = useState("");
    const [modelSource, setModelSource] = useState("");
    const [groqApiKey, setGroqApiKey] = useState("");
    const [groqModel, setGroqModel] = useState("");

    // New Settings
    const [ollamaModel, setOllamaModel] = useState("");
    const [redisUrl, setRedisUrl] = useState("");
    const [secretKey, setSecretKey] = useState("");
    const [algorithm, setAlgorithm] = useState("");
    const [telegramBotToken, setTelegramBotToken] = useState("");

    const [savingSettings, setSavingSettings] = useState(false);
    const [isEditingSettings, setIsEditingSettings] = useState(false);
    const [settingsLoaded, setSettingsLoaded] = useState(false);

    const fetchSettings = async (token: string) => {
        try {
            const res = await fetch("http://localhost:8000/api/admin/settings", {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.telegram_webhook_url) setWebhookUrl(data.telegram_webhook_url);
                if (data.journal_base_path) setJournalBasePath(data.journal_base_path);
                if (data.model_source) setModelSource(data.model_source);
                if (data.groq_api_key) setGroqApiKey(data.groq_api_key);
                if (data.groq_model) setGroqModel(data.groq_model);

                if (data.ollama_model) setOllamaModel(data.ollama_model);
                if (data.redis_url) setRedisUrl(data.redis_url);
                if (data.secret_key) setSecretKey(data.secret_key);
                if (data.algorithm) setAlgorithm(data.algorithm);
                if (data.telegram_bot_token) setTelegramBotToken(data.telegram_bot_token);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setSettingsLoaded(true);
        }
    };

    const [syncing, setSyncing] = useState(false);
    const [syncResult, setSyncResult] = useState<{ message: string, success: boolean } | null>(null);

    const handleLogout = () => {
        localStorage.removeItem("access_token");
        router.push("/login");
    };

    const handleSaveSettings = async (e: React.FormEvent) => {
        e.preventDefault();

        setSavingSettings(true);
        const token = localStorage.getItem("access_token");
        try {
            const res = await fetch("http://localhost:8000/api/admin/settings", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    telegram_webhook_url: webhookUrl || null,
                    journal_base_path: journalBasePath || null,
                    model_source: modelSource || null,
                    groq_api_key: groqApiKey || null,
                    groq_model: groqModel || null,
                    ollama_model: ollamaModel || null,
                    redis_url: redisUrl || null,
                    secret_key: secretKey || null,
                    algorithm: algorithm || null,
                    telegram_bot_token: telegramBotToken || null,
                })
            });
            if (res.ok) {
                setSyncResult({ message: "System settings saved successfully.", success: true });
                setIsEditingSettings(false);
            } else {
                setSyncResult({ message: "Failed to save settings.", success: false });
            }
        } catch (err) {
            setSyncResult({ message: "Network error occurred.", success: false });
        } finally {
            setSavingSettings(false);
            setTimeout(() => setSyncResult(null), 3000);
        }
    };

    const handleSyncWebhooks = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!webhookUrl) return;
        setSyncing(true);
        setSyncResult(null);
        const token = localStorage.getItem("access_token");
        try {
            const res = await fetch("http://localhost:8000/api/admin/sync-webhooks", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({ webhook_url: webhookUrl })
            });
            const data = await res.json();
            if (res.ok) {
                setSyncResult({ message: `Success! Synced ${data.details?.success_count || 0} bots.`, success: true });
            } else {
                setSyncResult({ message: `Failed: ${data.detail || 'Unknown error'}`, success: false });
            }
        } catch (err) {
            setSyncResult({ message: "Network error occurred.", success: false });
        } finally {
            setSyncing(false);
            setTimeout(() => setSyncResult(null), 5000);
        }
    };

    const handleAddUser = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = localStorage.getItem("access_token");
        try {
            const res = await fetch("http://localhost:8000/api/users/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    username: newUsername,
                    password: newPassword,
                    role: "user"
                })
            });

            if (res.ok) {
                setNewUsername("");
                setNewPassword("");
                fetchUsers(token!);
            }
        } catch (err) {
            console.error(err);
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
                        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-red-400 to-orange-400 bg-clip-text text-transparent">
                            Admin Control Panel
                        </h1>
                        <p className="text-zinc-400 mt-1">
                            System Users Management
                        </p>
                    </div>
                    <div className="flex gap-4">
                        <Link
                            href="/dashboard"
                            className="px-4 py-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-lg text-sm font-medium transition-colors"
                        >
                            Back to My Agents
                        </Link>
                        <button
                            onClick={handleLogout}
                            className="px-4 py-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-lg text-sm font-medium transition-colors"
                        >
                            Sign Out
                        </button>
                    </div>
                </header>

                {syncResult && (
                    <div className={`mb-8 p-4 rounded-lg border ${syncResult.success ? 'bg-green-500/10 border-green-500/50 text-green-400' : 'bg-red-500/10 border-red-500/50 text-red-400'}`}>
                        {syncResult.message}
                    </div>
                )}

                {settingsLoaded && (!journalBasePath || !groqModel || !ollamaModel || !redisUrl || !secretKey || !algorithm) && (
                    <div className="mb-8 p-4 rounded-lg border bg-yellow-500/10 border-yellow-500/50 text-yellow-400">
                        <strong>Warning:</strong> Core system settings are missing. Please edit the settings below to ensure backend stability.
                    </div>
                )}

                <section className="space-y-8">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
                        <h2 className="text-xl font-semibold mb-4">Add New User</h2>
                        <form onSubmit={handleAddUser} className="flex gap-4 items-end">
                            <div className="flex-1 space-y-1">
                                <label className="text-xs text-zinc-400">Username</label>
                                <input
                                    required
                                    type="text"
                                    value={newUsername}
                                    onChange={e => setNewUsername(e.target.value)}
                                    className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-red-500 outline-none"
                                />
                            </div>
                            <div className="flex-1 space-y-1">
                                <label className="text-xs text-zinc-400">Password</label>
                                <input
                                    required
                                    type="password"
                                    value={newPassword}
                                    onChange={e => setNewPassword(e.target.value)}
                                    className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-red-500 outline-none"
                                />
                            </div>
                            <button type="submit" className="px-5 py-2.5 bg-red-600 hover:bg-red-500 rounded-lg text-sm font-medium transition-colors h-[42px]">
                                Create User
                            </button>
                        </form>
                    </div>

                    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-semibold">System Settings</h2>
                            <div className="flex items-center gap-3">
                                {!isEditingSettings && (
                                    <button
                                        onClick={() => setIsEditingSettings(true)}
                                        className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs font-medium transition-colors border border-zinc-700"
                                    >
                                        Edit Settings
                                    </button>
                                )}
                                <form onSubmit={handleSyncWebhooks}>
                                    <button
                                        type="submit"
                                        disabled={syncing}
                                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800/50 rounded-lg text-xs font-medium transition-colors border border-indigo-500"
                                    >
                                        {syncing ? "Syncing..." : "Sync Webhooks Now"}
                                    </button>
                                </form>
                            </div>
                        </div>

                        {isEditingSettings ? (
                            <form onSubmit={handleSaveSettings} className="space-y-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Telegram Webhook URL</label>
                                    <input
                                        type="url"
                                        placeholder="https://your-id.ngrok-free.app"
                                        value={webhookUrl}
                                        onChange={e => setWebhookUrl(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                    <p className="text-[10px] text-zinc-500">Leave blank to disable. Syncing applies this to Telegram API.</p>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Journal Base Directory Path</label>
                                    <input
                                        required
                                        type="text"
                                        placeholder="data/journal"
                                        value={journalBasePath}
                                        onChange={e => setJournalBasePath(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                    <p className="text-[10px] text-zinc-500">Root folder where agent files are written to.</p>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Global Model Source</label>
                                    <select
                                        value={modelSource}
                                        onChange={e => setModelSource(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none appearance-none"
                                    >
                                        <option value="cloud">Cloud (Groq)</option>
                                        <option value="local">Local (Ollama)</option>
                                    </select>
                                    <p className="text-[10px] text-zinc-500">Default fallback source if an integration omits it.</p>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Groq API Key</label>
                                    <input
                                        type="password"
                                        placeholder="gsk_..."
                                        value={groqApiKey}
                                        onChange={e => setGroqApiKey(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                    <p className="text-[10px] text-zinc-500">Required if using Cloud models.</p>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Groq Model</label>
                                    <input
                                        type="text"
                                        placeholder="llama-3.3-70b-versatile"
                                        value={groqModel}
                                        onChange={e => setGroqModel(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Ollama Local Model</label>
                                    <input
                                        type="text"
                                        placeholder="llama3"
                                        value={ollamaModel}
                                        onChange={e => setOllamaModel(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                    <p className="text-[10px] text-zinc-500">Required if using Local models.</p>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Global Fallback Bot Token (Optional)</label>
                                    <input
                                        type="password"
                                        placeholder="12345:ABCDE..."
                                        value={telegramBotToken}
                                        onChange={e => setTelegramBotToken(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                    <p className="text-[10px] text-zinc-500">Used if a background job cannot determine the user's specific bot.</p>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-zinc-400">Redis URL</label>
                                    <input
                                        type="text"
                                        placeholder="redis://localhost:6379/0"
                                        value={redisUrl}
                                        onChange={e => setRedisUrl(e.target.value)}
                                        className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                        <label className="text-xs text-zinc-400">JWT Secret Key</label>
                                        <input
                                            type="password"
                                            value={secretKey}
                                            onChange={e => setSecretKey(e.target.value)}
                                            className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs text-zinc-400">JWT Algorithm</label>
                                        <input
                                            type="text"
                                            value={algorithm}
                                            onChange={e => setAlgorithm(e.target.value)}
                                            className="w-full bg-black border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                        />
                                    </div>
                                </div>
                                <div className="flex gap-3 pt-2">
                                    <button
                                        type="button"
                                        onClick={() => setIsEditingSettings(false)}
                                        className="flex-1 py-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium transition-colors"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        disabled={savingSettings}
                                        className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
                                    >
                                        {savingSettings ? "Saving..." : "Save Settings"}
                                    </button>
                                </div>
                            </form>
                        ) : (
                            <div className="space-y-0 text-sm border border-zinc-800 rounded-xl overflow-hidden">
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Telegram Webhook URL</span>
                                    <span className="col-span-2 text-zinc-200">{webhookUrl || <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Journal Base Path</span>
                                    <span className="col-span-2 text-zinc-200">{journalBasePath || <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Global Model Source</span>
                                    <span className="col-span-2 text-zinc-200">{modelSource === 'cloud' ? 'Cloud (Groq)' : 'Local (Ollama)'}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Groq API Key</span>
                                    <span className="col-span-2 text-zinc-200">{groqApiKey ? "••••••••••••••••" : <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Groq Model</span>
                                    <span className="col-span-2 text-zinc-200">{groqModel || <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Ollama Model</span>
                                    <span className="col-span-2 text-zinc-200">{ollamaModel || <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Global Bot Token</span>
                                    <span className="col-span-2 text-zinc-200">{telegramBotToken ? "••••••••••••••••" : <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">Redis URL</span>
                                    <span className="col-span-2 text-zinc-200">{redisUrl || <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 border-b border-zinc-800/50 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">JWT Secret</span>
                                    <span className="col-span-2 text-zinc-200">{secretKey ? "••••••••••••••••" : <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-4 p-4 hover:bg-zinc-800/20">
                                    <span className="text-zinc-400 font-medium tracking-wide text-xs uppercase">JWT Algorithm</span>
                                    <span className="col-span-2 text-zinc-200">{algorithm || <span className="text-zinc-600 italic">Not configured</span>}</span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
                        <h2 className="text-xl font-semibold mb-4">System Users</h2>
                        <div className="border border-zinc-800 rounded-xl overflow-hidden">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-zinc-950 border-b border-zinc-800 text-zinc-400">
                                    <tr>
                                        <th className="px-4 py-3 font-medium">Username</th>
                                        <th className="px-4 py-3 font-medium">Role</th>
                                        <th className="px-4 py-3 font-medium">Integrations</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-800">
                                    {allUsers.map(u => (
                                        <tr key={u.username} className="hover:bg-zinc-800/50">
                                            <td className="px-4 py-3 font-medium">{u.username}</td>
                                            <td className="px-4 py-3">
                                                <span className={`px-2 py-1 rounded text-xs ${u.role === 'admin' ? 'bg-red-500/20 text-red-300' : 'bg-zinc-800 text-zinc-300'}`}>
                                                    {u.role}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-zinc-400">
                                                {u.integrations?.length || 0} configured
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
}
