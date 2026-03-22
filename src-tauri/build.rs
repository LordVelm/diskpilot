fn main() {
    // Only embed requireAdministrator manifest on release builds.
    // Dev builds run without admin — WMI reads still work, mutations will fail gracefully.
    #[cfg(target_os = "windows")]
    {
        let mut win_attrs = tauri_build::WindowsAttributes::new();
        if !cfg!(debug_assertions) {
            win_attrs = win_attrs.app_manifest(include_str!("diskpilot.exe.manifest"));
        }
        let attrs = tauri_build::Attributes::new().windows_attributes(win_attrs);
        tauri_build::try_build(attrs).expect("failed to run tauri-build");
    }

    #[cfg(not(target_os = "windows"))]
    {
        tauri_build::build()
    }
}
