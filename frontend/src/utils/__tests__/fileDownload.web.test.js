/**
 * ind3-fix3 — regression: on web (non-native) downloadBlob must keep the
 * classic <a download> anchor flow, since routing all download call-sites
 * through it must not change web behavior.
 */
import { downloadBlob } from '../fileDownload';
import { Capacitor } from '@capacitor/core';

jest.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: jest.fn(() => false) },
}));
jest.mock('@capacitor/filesystem', () => ({
  Filesystem: { writeFile: jest.fn() },
  Directory: { Documents: 'DOCUMENTS' },
}));
jest.mock('@capacitor/share', () => ({ Share: { share: jest.fn() } }));

describe('downloadBlob (web path)', () => {
  let clickSpy;

  beforeEach(() => {
    window.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
    window.URL.revokeObjectURL = jest.fn();
    clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });

  afterEach(() => {
    clickSpy.mockRestore();
  });

  test('uses anchor download on web and never touches Filesystem/Share', async () => {
    const { Filesystem } = require('@capacitor/filesystem');
    const { Share } = require('@capacitor/share');
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });

    const res = await downloadBlob(blob, 'test.pdf', 'application/pdf');

    expect(Capacitor.isNativePlatform).toHaveBeenCalled();
    expect(window.URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    expect(Filesystem.writeFile).not.toHaveBeenCalled();
    expect(Share.share).not.toHaveBeenCalled();
    expect(res).toEqual({ success: true, filename: 'test.pdf' });
  });

  test('anchor gets the download filename attribute', async () => {
    let capturedDownload = null;
    clickSpy.mockImplementation(function () { capturedDownload = this.download; });
    await downloadBlob(new Blob(['x']), 'דוח.pdf', 'application/pdf');
    expect(capturedDownload).toBe('דוח.pdf');
  });
});
