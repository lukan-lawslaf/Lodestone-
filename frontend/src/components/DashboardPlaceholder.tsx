import React, { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';

interface DashboardPlaceholderProps {
  userId: string;
  userEmail: string;
  onLogout: () => void;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEMO_PROBLEM_ID = 'demo_001';
const DEMO_PROBLEM_TEXT = 'Write a function that returns the sum of a list of numbers.';

const getBoilerplate = (problemId: string, problemText: string) => {
  if (problemId === 'demo_001' || problemId === 'prob_001') {
    return `def sum_list(numbers):\n    # ${problemText}\n    pass\n`;
  }
  if (problemId === 'prob_cp7' || problemId === 'prob_cp8') {
    return `def find_max(lst):\n    # ${problemText}\n    pass\n`;
  }
  return `# ${problemText}\n# Write your code here\n`;
};

const DEFAULT_CODE_BOILERPLATE = getBoilerplate(DEMO_PROBLEM_ID, DEMO_PROBLEM_TEXT);

export const DashboardPlaceholder: React.FC<DashboardPlaceholderProps> = ({ userId, userEmail, onLogout }) => {
  // Sidebar State
  const [activeFile, setActiveFile] = useState<'main.py' | 'config.py' | 'db.py' | null>(null);

  // Session & Workflow State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [editorUnlocked, setEditorUnlocked] = useState(false);
  const [phase, setPhase] = useState<'setup' | 'clarification' | 'coding' | 'submitted'>('setup');
  
  // Socratic Chat State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  
  // Code Editor State
  const [code, setCode] = useState(DEFAULT_CODE_BOILERPLATE);
  const [consoleOutput, setConsoleOutput] = useState<{ stdout: string; stderr: string; exitCode: number } | null>(null);
  
  // Final Submission State
  const [submitResult, setSubmitResult] = useState<{ match: boolean; mismatchNote: string | null; reflection: string; sks: any } | null>(null);
  
  // Loaders & Error States
  const [apiLoading, setApiLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Reset session and start fresh
  const handleResetSession = () => {
    setActiveFile(null);
    setSessionId(null);
    setEditorUnlocked(false);
    setPhase('setup');
    setChatMessages([]);
    setChatInput('');
    setCode(getBoilerplate(DEMO_PROBLEM_ID, DEMO_PROBLEM_TEXT));
    setConsoleOutput(null);
    setSubmitResult(null);
    setServerError(null);
  };

  // Helper function to handle fetch with backend-down checks
  const apiCall = async (endpoint: string, options: RequestInit) => {
    setServerError(null);
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned status ${response.status}`);
      }

      return await response.json();
    } catch (err: any) {
      console.error('API Error: ', err);
      const isConnectionError = err.message.includes('Failed to fetch') || err.message.includes('NetworkError') || err.message.includes('typeerror');
      const errorMsg = isConnectionError
        ? 'Backend not reachable. Start the FastAPI server on port 8000.'
        : err.message || 'An unexpected error occurred.';
      setServerError(errorMsg);
      throw err;
    }
  };

  // Start Session (triggered on main.py click)
  const handleStartSession = async () => {
    if (activeFile === 'main.py') return; // session already active
    
    setActiveFile('main.py');
    setApiLoading(true);
    setServerError(null);

    try {
      const data = await apiCall('/session/start', {
        method: 'POST',
        body: JSON.stringify({
          student_id: userId,
          problem_id: DEMO_PROBLEM_ID,
          problem_text: DEMO_PROBLEM_TEXT,
        }),
      });

      setSessionId(data.session_id);
      setPhase('clarification');
      setEditorUnlocked(false);
      setChatMessages(data.ai_message ? [{ role: 'assistant', content: data.ai_message }] : []);
      setCode(getBoilerplate(DEMO_PROBLEM_ID, DEMO_PROBLEM_TEXT));
    } catch (err) {
      // API call helper sets serverError. Reset active file to let them retry.
      setActiveFile(null);
    } finally {
      setApiLoading(false);
    }
  };

  // Handle Socratic Chat message submit
  const handleSendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || apiLoading || !sessionId) return;

    const messageText = chatInput.trim();
    setChatInput('');
    setChatMessages((prev) => [...prev, { role: 'user', content: messageText }]);
    setApiLoading(true);

    try {
      if (!editorUnlocked) {
        // Spec clarification phase
        const data = await apiCall(`/session/${sessionId}/spec`, {
          method: 'POST',
          body: JSON.stringify({
            student_input: messageText,
          }),
        });

        if (data.editor_unlocked) {
          setEditorUnlocked(true);
          setPhase('coding');
          setChatMessages((prev) => [
            ...prev,
            { 
              role: 'assistant', 
              content: data.ai_message || 'Perfect! Your specification is approved. The editor is now unlocked. Let\'s write the code!' 
            }
          ]);
        } else {
          setChatMessages((prev) => [
            ...prev,
            { role: 'assistant', content: data.ai_message || 'Can you elaborate on that?' }
          ]);
        }
      } else {
        // Coding phase chat
        const data = await apiCall(`/session/${sessionId}/code/chat`, {
          method: 'POST',
          body: JSON.stringify({
            student_message: messageText,
          }),
        });

        setChatMessages((prev) => [
          ...prev,
          { role: 'assistant', content: data.ai_message }
        ]);
      }
    } catch (err) {
      // Error handled in apiCall (serverError set)
    } finally {
      setApiLoading(false);
    }
  };

  // Run Code
  const handleRunCode = async () => {
    if (!sessionId || apiLoading) return;

    setApiLoading(true);
    setConsoleOutput(null);

    try {
      const data = await apiCall(`/session/${sessionId}/code/run`, {
        method: 'POST',
        body: JSON.stringify({
          code: code,
          language: 'python',
        }),
      });

      setConsoleOutput({
        stdout: data.stdout,
        stderr: data.stderr,
        exitCode: data.exit_code,
      });

      // If compilation failed and Socratic hint is provided, append it to the chat
      if (data.exit_code !== 0 && data.ai_message) {
        setChatMessages((prev) => [
          ...prev,
          { role: 'assistant', content: data.ai_message }
        ]);
      }
    } catch (err) {
      // Error handled in apiCall
    } finally {
      setApiLoading(false);
    }
  };

  // Submit Code
  const handleSubmitCode = async () => {
    if (!sessionId || apiLoading) return;

    setApiLoading(true);

    try {
      const data = await apiCall(`/session/${sessionId}/submit`, {
        method: 'POST',
        body: JSON.stringify({
          final_code: code,
        }),
      });

      setSubmitResult({
        match: data.match,
        mismatchNote: data.mismatch_note,
        reflection: data.reflection,
        sks: data.sks_update,
      });
      setPhase('submitted');
    } catch (err) {
      // Error handled in apiCall
    } finally {
      setApiLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-zinc-950 text-zinc-100 flex flex-col font-body">
      {/* Dashboard Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-md px-6 py-4 flex justify-between items-center z-10">
        <div className="flex items-center gap-3">
          <span className="font-heading text-lg tracking-tight font-medium text-white">
            Lodestone® IDE
          </span>
          <span className="text-[20px] leading-none select-none text-zinc-400">
            ✳︎
          </span>
          {sessionId && (
            <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-full text-xs">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-mono text-zinc-300">Session Active</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex flex-col text-right">
            <span className="text-xs text-zinc-400">Logged in as</span>
            <span className="text-sm font-medium text-zinc-200">{userEmail}</span>
          </div>
          <button 
            onClick={onLogout}
            className="border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 hover:text-white text-zinc-300 px-4 py-1.5 rounded-lg text-sm transition-all"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Workspace Area */}
      <main className="flex-1 flex flex-col md:flex-row p-6 gap-6 max-w-7xl mx-auto w-full overflow-hidden">
        {/* Sidebar Workspace Explorer */}
        <aside className="w-full md:w-64 border border-zinc-800 bg-zinc-900/30 rounded-2xl p-5 flex flex-col justify-between shrink-0">
          <div className="space-y-6">
            <div>
              <h3 className="text-xs uppercase tracking-wider text-zinc-500 font-mono mb-3">Workspace</h3>
              <div className="space-y-2">
                {/* main.py - Clickable to start session */}
                <button 
                  onClick={handleStartSession}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium flex items-center justify-between border transition-all ${
                    activeFile === 'main.py'
                      ? 'bg-zinc-900 text-zinc-100 border-zinc-700'
                      : 'hover:bg-zinc-900/40 text-zinc-400 border-transparent hover:text-zinc-200'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span>📄</span> main.py
                  </div>
                  {activeFile !== 'main.py' && (
                    <span className="text-[10px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded font-mono uppercase">
                      Start
                    </span>
                  )}
                </button>


              </div>
            </div>

            {/* SKS Status Details */}
            {submitResult && submitResult.sks && (
              <div className="border-t border-zinc-800 pt-4">
                <h3 className="text-xs uppercase tracking-wider text-zinc-500 font-mono mb-3">Knowledge State</h3>
                <div className="text-xs space-y-3 font-mono">

                  {/* avg_hint_level_needed */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-3 space-y-1">
                    <span className="text-zinc-500 block">avg_hint_level:</span>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all"
                          style={{ width: `${Math.min(((submitResult.sks.avg_hint_level_needed ?? 1) / 5) * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-emerald-400 font-semibold shrink-0">
                        {(submitResult.sks.avg_hint_level_needed ?? 1).toFixed(1)}/5
                      </span>
                    </div>
                  </div>

                  {/* topic_scores */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-3 space-y-1.5">
                    <span className="text-zinc-500 block">topic_scores:</span>
                    {Object.keys(submitResult.sks.topic_scores ?? {}).length === 0 ? (
                      <span className="text-zinc-600 italic">none yet</span>
                    ) : (
                      Object.entries(submitResult.sks.topic_scores).map(([topic, score]: any) => (
                        <div key={topic} className="flex justify-between items-center">
                          <span className="text-zinc-400">{topic}</span>
                          <span className="text-emerald-400 font-semibold">{(score * 100).toFixed(0)}%</span>
                        </div>
                      ))
                    )}
                  </div>

                  {/* mistake_patterns */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-3 space-y-1.5">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">mistake_patterns:</span>
                      <span className="text-amber-400 font-semibold">
                        {(submitResult.sks.mistake_patterns ?? []).length}
                      </span>
                    </div>
                    {(submitResult.sks.mistake_patterns ?? []).length > 0 && (
                      <ul className="space-y-1 mt-1">
                        {submitResult.sks.mistake_patterns.map((p: string, i: number) => (
                          <li key={i} className="text-zinc-400 text-[10px] leading-relaxed border-l-2 border-amber-500/40 pl-2">
                            {p}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                </div>
              </div>
            )}
          </div>

          <div className="border-t border-zinc-800 pt-4 mt-6">
            <div className="text-xs text-zinc-500 font-mono break-all space-y-1">
              <span className="block text-zinc-600">STUDENT_ID:</span>
              <span className="text-[10px] select-all">{userId}</span>
            </div>
            {sessionId && (
              <button 
                onClick={handleResetSession}
                className="w-full mt-4 text-xs font-mono text-zinc-500 hover:text-zinc-200 border border-zinc-800 bg-zinc-900/20 py-1 rounded hover:bg-zinc-800 transition-all"
              >
                Reset Session
              </button>
            )}
          </div>
        </aside>

        {/* Center Workspace Dashboard */}
        <div className="flex-1 flex flex-col gap-6 overflow-hidden">
          {/* Error Banner */}
          {serverError && (
            <div className="p-4 bg-rose-950/80 border border-rose-800 text-rose-200 font-body rounded-2xl flex items-start gap-3 shadow-lg">
              <span className="text-lg">⚠️</span>
              <div>
                <h4 className="font-heading font-medium text-sm">Server Communication Error</h4>
                <p className="text-xs text-rose-300/90 mt-0.5">{serverError}</p>
              </div>
            </div>
          )}

          {/* Workflow Stage Routing */}
          {phase === 'setup' ? (
            /* Setup Phase - Select File Banner */
            <section className="flex-1 border border-zinc-800 bg-zinc-900/10 rounded-[24px] p-8 flex flex-col justify-center items-center text-center relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-b from-transparent to-zinc-900/50" />
              <div className="relative z-10 max-w-md space-y-6">
                <span className="text-4xl animate-bounce inline-block">👈</span>
                <h2 className="font-heading text-3xl text-white tracking-tight">
                  Start your Socratic Session
                </h2>
                <p className="font-body text-zinc-400 text-base leading-relaxed">
                  Select <strong className="text-zinc-200 font-medium">main.py</strong> in the sidebar workspace. 
                  This will generate your Socratic context using the FastAPI backend and spin up your tutoring terminal.
                </p>
                {apiLoading && (
                  <div className="flex items-center justify-center gap-2 text-zinc-400 font-mono text-sm">
                    <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Initializing session graph...</span>
                  </div>
                )}
              </div>
            </section>
          ) : phase === 'submitted' && submitResult ? (
            /* Submitted Phase - Reflection / Closing Summary Card */
            <section className="flex-1 border-2 border-emerald-500/20 bg-zinc-900/20 rounded-[28px] p-6 sm:p-8 flex flex-col justify-between text-left overflow-y-auto">
              <div className="space-y-6">
                <div className="flex justify-between items-start gap-4">
                  <div>
                    <span className="font-mono text-xs uppercase tracking-widest text-emerald-400 block mb-2 font-semibold">
                      Evaluation Complete
                    </span>
                    <h2 className="font-heading text-3xl sm:text-4xl text-white tracking-tight leading-none">
                      Lodestone Reflection Card
                    </h2>
                  </div>
                  <button 
                    onClick={handleResetSession}
                    className="bg-emerald-500 hover:bg-emerald-600 text-black font-heading font-medium text-sm px-4 py-2 rounded-xl transition-all"
                  >
                    Start New Session
                  </button>
                </div>

                {/* Match / Mismatch banner */}
                <div className={`p-5 rounded-2xl border ${
                  submitResult.match 
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-200' 
                    : 'bg-amber-500/10 border-amber-500/20 text-amber-200'
                }`}>
                  <h3 className="font-heading text-lg font-medium flex items-center gap-2">
                    {submitResult.match ? '✅ Code Matches Specification' : '⚠️ Code-Specification Mismatch'}
                  </h3>
                  <p className="font-body text-sm mt-2 leading-relaxed opacity-90">
                    {submitResult.match 
                      ? 'Great job! The final code correctly fulfills all conditions outlined in your specification.' 
                      : submitResult.mismatchNote || 'Your code differs from the finalized specification. Review the mismatch logs below.'
                    }
                  </p>
                </div>

                {/* Reflection box */}
                <div className="border border-zinc-800 bg-zinc-950 p-6 rounded-2xl space-y-3">
                  <h4 className="font-heading text-sm text-zinc-400 uppercase tracking-widest font-semibold">
                    Socratic Reflection Prompt
                  </h4>
                  <p className="font-body text-base text-zinc-100 italic leading-relaxed">
                    "{submitResult.reflection}"
                  </p>
                </div>

                {/* Code summary */}
                <div className="border border-zinc-800 bg-zinc-950 rounded-2xl overflow-hidden">
                  <div className="bg-zinc-900 px-4 py-2.5 font-mono text-xs text-zinc-400 border-b border-zinc-800">
                    Submitted Code (main.py)
                  </div>
                  <pre className="p-4 font-mono text-xs text-zinc-300 overflow-x-auto max-h-48 leading-relaxed">
                    {code}
                  </pre>
                </div>
              </div>

              <div className="mt-8 border-t border-zinc-800 pt-6 text-xs text-zinc-500 font-mono flex flex-col sm:flex-row justify-between gap-4">
                <div>STUDENT_ID: {userId}</div>
                <div>SESSION_ID: {sessionId}</div>
              </div>
            </section>
          ) : (
            /* Active Session Layout (Clarification / Coding Phase) */
            <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0">
              {/* Left Column: Monaco Code Editor Panel */}
              <div className="flex-1 flex flex-col border border-zinc-800 bg-zinc-900/10 rounded-[24px] overflow-hidden min-h-0">
                <div className="bg-zinc-900/80 px-5 py-3 border-b border-zinc-800 flex justify-between items-center shrink-0">
                  <span className="font-heading text-sm text-zinc-200 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-indigo-500" />
                    main.py
                  </span>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded ${
                      editorUnlocked ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-500'
                    }`}>
                      {editorUnlocked ? 'Editor Unlocked' : 'Editor Locked'}
                    </span>
                  </div>
                </div>

                <div className="flex-1 relative min-h-[300px]">
                  {/* Grayed-out Locked overlay */}
                  {!editorUnlocked && (
                    <div className="absolute inset-0 bg-zinc-950/80 backdrop-blur-[2px] z-20 flex flex-col items-center justify-center p-6 text-center">
                      <span className="text-3xl mb-3">🔒</span>
                      <h4 className="font-heading text-lg text-white mb-2">Complete your spec to unlock the editor</h4>
                      <p className="font-body text-xs text-zinc-400 max-w-xs leading-relaxed">
                        Lodestone requires defining your specifications first. Solve clarification questions with the tutor on the right.
                      </p>
                    </div>
                  )}

                  {/* Monaco Editor Container */}
                  <div className="absolute inset-0 w-full h-full">
                    {editorUnlocked ? (
                      <Editor
                        height="100%"
                        language="python"
                        theme="vs-dark"
                        value={code}
                        onChange={(val) => setCode(val || '')}
                        options={{
                          quickSuggestions: false,
                          suggestOnTriggerCharacters: false,
                          minimap: { enabled: false },
                          fontSize: 14,
                          lineNumbers: 'on',
                          tabSize: 4,
                          scrollbar: {
                            verticalScrollbarSize: 8,
                            horizontalScrollbarSize: 8,
                          },
                        }}
                      />
                    ) : (
                      // Render passive mockup when locked
                      <pre className="p-5 font-mono text-sm text-zinc-600 text-left opacity-30 select-none">
                        {code}
                      </pre>
                    )}
                  </div>
                </div>

                {/* Editor Action Buttons & Console Panel (Only when unlocked) */}
                {editorUnlocked && (
                  <div className="border-t border-zinc-800 bg-zinc-950/40 p-4 space-y-4 shrink-0">
                    <div className="flex justify-between items-center gap-4">
                      {/* Console Panel Label */}
                      <span className="font-mono text-xs text-zinc-500 uppercase tracking-wider">Console Terminal</span>
                      <div className="flex items-center gap-3">
                        {/* Run Button */}
                        <button
                          onClick={handleRunCode}
                          disabled={apiLoading}
                          className="bg-zinc-800 hover:bg-zinc-700 text-white font-heading text-sm font-medium px-4 py-1.5 rounded-lg transition-all disabled:opacity-50 flex items-center gap-2"
                        >
                          {apiLoading ? (
                            <span className="w-3 h-3 border-2 border-zinc-400 border-t-white rounded-full animate-spin" />
                          ) : '▶'}
                          <span>Run Code</span>
                        </button>
                        {/* Submit Button */}
                        <button
                          onClick={handleSubmitCode}
                          disabled={apiLoading}
                          className="bg-indigo-500 hover:bg-indigo-600 text-white font-heading text-sm font-medium px-4 py-1.5 rounded-lg transition-all disabled:opacity-50 flex items-center gap-2"
                        >
                          {apiLoading ? (
                            <span className="w-3 h-3 border-2 border-indigo-200 border-t-white rounded-full animate-spin" />
                          ) : '✓'}
                          <span>Submit</span>
                        </button>
                      </div>
                    </div>

                    {/* Console Output Screen */}
                    <div className="bg-zinc-950 border border-zinc-850 p-4 rounded-xl font-mono text-xs min-h-[90px] max-h-[160px] overflow-y-auto text-left leading-relaxed">
                      {consoleOutput ? (
                        <div className="space-y-1">
                          <div className="flex justify-between text-zinc-500 border-b border-zinc-900 pb-1 mb-1">
                            <span>Process Terminated</span>
                            <span>Exit Code: {consoleOutput.exitCode}</span>
                          </div>
                          {consoleOutput.stdout && (
                            <div className="text-zinc-200 whitespace-pre-wrap">{consoleOutput.stdout}</div>
                          )}
                          {consoleOutput.stderr && (
                            <div className="text-rose-400 whitespace-pre-wrap">{consoleOutput.stderr}</div>
                          )}
                          {!consoleOutput.stdout && !consoleOutput.stderr && (
                            <div className="text-zinc-500 italic">No console logs returned.</div>
                          )}
                        </div>
                      ) : (
                        <div className="text-zinc-600 italic">Click "Run Code" to compile and execute program output.</div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Right Column: Socratic Chat Panel */}
              <div className="w-full lg:w-96 border border-zinc-800 bg-zinc-900/10 rounded-[24px] flex flex-col justify-between overflow-hidden min-h-[350px] lg:min-h-0 lg:h-full">
                {/* Chat Header */}
                <div className="bg-zinc-900/85 border-b border-zinc-800 px-5 py-3 flex items-center gap-2.5 shrink-0 text-left">
                  <span className="text-indigo-400 text-lg select-none">✳︎</span>
                  <div>
                    <h3 className="font-heading text-sm text-white font-medium leading-none">Socratic Chat</h3>
                    <span className="text-[10px] text-zinc-500 font-mono">Powered by Lodestone Engine</span>
                  </div>
                </div>

                {/* Messages Panel */}
                <div className="flex-1 overflow-y-auto p-5 space-y-4 text-left min-h-0 bg-black/[0.05]">
                  {chatMessages.map((msg, idx) => (
                    <div 
                      key={idx}
                      className={`flex flex-col max-w-[85%] ${
                        msg.role === 'user' ? 'ml-auto items-end' : 'mr-auto items-start'
                      }`}
                    >
                      <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">
                        {msg.role === 'user' ? 'You' : 'Lodestone'}
                      </span>
                      <div className={`p-4 rounded-2xl text-[14px] leading-relaxed font-body ${
                        msg.role === 'user' 
                          ? 'bg-indigo-500 text-white rounded-tr-none shadow-md shadow-indigo-500/10'
                          : 'bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-tl-none'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  ))}

                  {apiLoading && chatMessages.length > 0 && chatMessages[chatMessages.length - 1].role === 'user' && (
                    <div className="flex flex-col items-start max-w-[85%] mr-auto">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">
                        Lodestone
                      </span>
                      <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-2xl rounded-tl-none flex items-center gap-2">
                        <span className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  )}

                  <div ref={chatEndRef} />
                </div>

                {/* Chat Input Field */}
                <form 
                  onSubmit={handleSendChatMessage}
                  className="p-4 border-t border-zinc-800 bg-zinc-950/40 flex items-center gap-2 shrink-0"
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={apiLoading}
                    placeholder={
                      !editorUnlocked 
                        ? 'Confirm / clarify your spec...' 
                        : 'Ask your tutor a question...'
                    }
                    className="flex-1 bg-zinc-900/80 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-zinc-100 focus:outline-none focus:border-zinc-700 placeholder-zinc-500 disabled:opacity-50"
                  />
                  <button
                    type="submit"
                    disabled={apiLoading || !chatInput.trim()}
                    className="bg-white hover:bg-zinc-200 text-black text-sm font-medium px-4 py-2.5 rounded-xl transition-all disabled:opacity-40"
                  >
                    Send
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
