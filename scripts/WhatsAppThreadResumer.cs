using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
internal static class WhatsAppThreadResumer {
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, uint id);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool QueryFullProcessImageName(IntPtr process, uint flags, StringBuilder path, ref uint size);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenThread(uint access, bool inherit, uint id);
    [DllImport("kernel32.dll", SetLastError=true)] static extern uint GetProcessIdOfThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError=true)] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    static int End(int result) {
        try { File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,
            "resumer-result.txt"), result.ToString()); } catch {}
        return result;
    }
    static int Main(string[] args) {
        uint processId, threadId;
        if (args.Length != 4 || args[0] != "-p" || args[2] != "-tid" ||
            !uint.TryParse(args[1], out processId) || !uint.TryParse(args[3], out threadId))
            return End(64);
        try {
            IntPtr process = OpenProcess(0x1000, false, processId);
            if (process == IntPtr.Zero) return End(65);
            try {
                var executable = new StringBuilder(2048);
                uint size = (uint)executable.Capacity;
                if (!QueryFullProcessImageName(process, 0, executable, ref size)) return End(66);
                string path = executable.ToString();
                if (!string.Equals(Path.GetFileName(path), "WhatsApp.Root.exe", StringComparison.OrdinalIgnoreCase) ||
                    !Path.GetDirectoryName(path).StartsWith(@"C:\Program Files\WindowsApps\5319275A.WhatsAppDesktop_",
                        StringComparison.OrdinalIgnoreCase))
                    return End(67);
            } finally { CloseHandle(process); }
            IntPtr thread = OpenThread(0x0802, false, threadId);
            if (thread == IntPtr.Zero) return End(68);
            try {
                if (GetProcessIdOfThread(thread) != processId) return End(69);
                return End(ResumeThread(thread) == 0xFFFFFFFF ? 70 : 0);
            } finally { CloseHandle(thread); }
        } catch { return End(71); }
    }
}
