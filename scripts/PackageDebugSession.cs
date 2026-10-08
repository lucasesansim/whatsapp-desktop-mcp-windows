using System;
using System.Runtime.InteropServices;
namespace ChatIATest {
    [ComImport, Guid("F27C3930-8029-4AD1-94E3-3DBA417810C1"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPackageDebugSettings {
        [PreserveSig] int EnableDebugging([MarshalAs(UnmanagedType.LPWStr)] string packageFullName,
            [MarshalAs(UnmanagedType.LPWStr)] string debuggerCommandLine, IntPtr environment);
        [PreserveSig] int DisableDebugging([MarshalAs(UnmanagedType.LPWStr)] string packageFullName);
    }
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager {
        [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string id,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments, uint options, out uint processId);
    }
    public static class WhatsAppActivation {
        public static uint Launch() {
            var manager = (IApplicationActivationManager)Activator.CreateInstance(
                Type.GetTypeFromCLSID(new Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")));
            try {
                uint pid;
                Marshal.ThrowExceptionForHR(manager.ActivateApplication(
                    "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", null, 0, out pid));
                return pid;
            } finally { Marshal.FinalReleaseComObject(manager); }
        }
    }
    public sealed class PackageDebugSession : IDisposable {
        private IPackageDebugSettings settings;
        private string package;
        private bool enabled;
        public int EnableResult { get; private set; }
        public PackageDebugSession(string packageFullName, string environment, string debuggerPath) {
            if (!packageFullName.StartsWith("5319275A.WhatsAppDesktop_") ||
                !packageFullName.EndsWith("_x64__cv1g1gvanyjgm"))
                throw new ArgumentException("Unexpected WhatsApp package.");
            package = packageFullName;
            settings = (IPackageDebugSettings)Activator.CreateInstance(
                Type.GetTypeFromCLSID(new Guid("B1AEC16F-2383-4852-B0E9-8F0B1DC66B4D")));
            IntPtr block = environment == null ? IntPtr.Zero : Marshal.StringToHGlobalUni(environment + "\0");
            try {
                EnableResult = settings.EnableDebugging(package, debuggerPath, block);
                Marshal.ThrowExceptionForHR(EnableResult);
                enabled = true;
            } catch {
                Marshal.FinalReleaseComObject(settings);
                settings = null;
                throw;
            } finally { Marshal.FreeHGlobal(block); }
        }
        public void Dispose() {
            if (settings == null) return;
            int result = 0;
            try {
                if (enabled) result = settings.DisableDebugging(package);
            } finally {
                Marshal.FinalReleaseComObject(settings);
                settings = null;
                enabled = false;
            }
            Marshal.ThrowExceptionForHR(result);
        }
    }
}
