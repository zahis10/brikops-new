const loadI18n = () => {
  jest.resetModules();
  return require('../index');
};

describe('i18n language persistence', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = 'he';
    jest.restoreAllMocks();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('normalizes a regional Arabic locale and updates the document', () => {
    const { getLanguage, setLanguage } = loadI18n();

    setLanguage('ar-EG');

    expect(getLanguage()).toBe('ar');
    expect(document.documentElement.lang).toBe('ar');
    expect(localStorage.getItem('brikops_lang')).toBe('ar');
  });

  test('restores a supported saved language on a fresh module load', () => {
    localStorage.setItem('brikops_lang', 'zh');

    const { getLanguage } = loadI18n();

    expect(getLanguage()).toBe('zh');
    expect(document.documentElement.lang).toBe('zh');
  });

  test('ignores an unknown saved language and starts in Hebrew', () => {
    localStorage.setItem('brikops_lang', 'xx');

    const { getLanguage } = loadI18n();

    expect(getLanguage()).toBe('he');
    expect(document.documentElement.lang).toBe('he');
  });

  test('swallows unavailable localStorage reads and writes', () => {
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    const i18n = loadI18n();
    expect(i18n.getLanguage()).toBe('he');

    jest.restoreAllMocks();
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });

    expect(() => i18n.setLanguage('ar')).not.toThrow();
    expect(i18n.getLanguage()).toBe('ar');
    expect(document.documentElement.lang).toBe('ar');
  });
});