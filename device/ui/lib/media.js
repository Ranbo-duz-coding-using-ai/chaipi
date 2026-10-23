'use strict';
/* USB drive mode and the display's microSD slot. The privileged parts (USB gadget, mounting) are in
   /opt/chaipi/bin/chaipi-media, which the image lets user chaipi run through sudo. It prints one JSON line. */
const fs = require('fs');
const { execFile } = require('child_process');

function media(helper, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    execFile('sudo', ['-n', helper].concat(args), { timeout: timeoutMs || 120000 }, (err, out, errOut) => {
      const last = String(out || '').trim().split('\n').pop();
      let msg = null; try { msg = JSON.parse(last); } catch (e) { /* not JSON */ }
      if (err && !(msg && msg.msg)) { reject(new Error((errOut || err.message).trim().split('\n').pop())); return; }
      resolve(msg || { msg: last });
    });
  });
}

/* USB gadget state from the kernel: "configured" once a computer has mounted ChAIpi as a drive. */
function usbConfigured() {
  try {
    for (const udc of fs.readdirSync('/sys/class/udc')) {
      if (fs.readFileSync('/sys/class/udc/' + udc + '/state', 'utf8').trim() === 'configured') return true;
    }
  } catch (e) { /* no UDC: dwc2 overlay missing */ }
  return false;
}

/* The TFT's slot shows up as a second MMC device (the boot card is mmcblk0). */
function sdPresent() {
  try { return fs.readdirSync('/sys/block').some(b => /^mmcblk[1-9]$/.test(b)); } catch (e) { return false; }
}

class Media {
  constructor(opts) { this.helper = opts.helper; this.log = opts.log || console.log; this.usbOn = false; this.sdInfo = ''; }
  async usbStart() { if (this.usbOn) return; this.usbOn = true; try { await media(this.helper, ['usb-start']); } catch (e) { this.usbOn = false; this.log('usb start:', e.message); throw e; } }
  async usbStop() { if (!this.usbOn) return 'USB drive mode off'; this.usbOn = false; const r = await media(this.helper, ['usb-stop']); return r.msg; }
  async sdImport() { const r = await media(this.helper, ['sd-import']); this.sdInfo = r.summary || this.sdInfo; return r.msg; }
  async sdExport() { const r = await media(this.helper, ['sd-export']); this.sdInfo = r.summary || this.sdInfo; return r.msg; }
  async sdEject() { const r = await media(this.helper, ['sd-eject']); return r.msg; }
  async sdBackup() { const r = await media(this.helper, ['sd-backup']); return r.msg; }
  async sdScan() { try { const r = await media(this.helper, ['sd-summary'], 30000); this.sdInfo = r.summary || ''; } catch (e) { this.sdInfo = ''; } }
  summary() { return this.sdInfo || 'SD card found'; }
}

module.exports = { Media, usbConfigured, sdPresent };
