namespace LightroomMcp.Controller;

/// <summary>lightroom-mcp error codes, in addition to the WinGuiMcp.Core codes. Documented in docs/errors.md.</summary>
public static class LrErrorCodes
{
    public const string ControllerUnavailable = "ControllerUnavailable";
    public const string ApprovalPending = "ApprovalPending";
    public const string ApprovalDenied = "ApprovalDenied";
    public const string ControllerCallFailed = "ControllerCallFailed";
    public const string PhotoMismatch = "PhotoMismatch";
    public const string ConfirmationRequired = "ConfirmationRequired";
    public const string ExternalControllerActive = "ExternalControllerActive";
    public const string ReadbackMismatch = "ReadbackMismatch";
    public const string ReadbackRequired = "ReadbackRequired";
    public const string SaveUnverified = "SaveUnverified";
    public const string UnknownParameter = "UnknownParameter";
    public const string SettingsNotFound = "SettingsNotFound";
}
