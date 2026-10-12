// Keys remain in this view only; never persist them in the browser store.
export function showRecoveryKey(container, key) {
  container.innerHTML =
    '<div class="notice"><strong>Save your recovery key</strong><p>This private key can reset your password. Keep it in your password manager or download it somewhere safe. It replaces any previous key.</p><label for="saved-recovery-key">Recovery key</label><input id="saved-recovery-key" readonly autocomplete="off"><button class="workspace-action" type="button">Download recovery key</button></div>';
  container.querySelector('input').value = key;
  container.querySelector('button').onclick = () => {
    const url = URL.createObjectURL(
      new Blob(
        [
          `Sentio password recovery key\n\n${key}\n\nKeep this private. Use Forgot password in Sentio. This key can be used once.\n`,
        ],
        { type: 'text/plain' },
      ),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sentio-recovery-key.txt';
    link.click();
    URL.revokeObjectURL(url);
  };
}
