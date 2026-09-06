import { installDomGuard } from '../domGuard';

describe('installDomGuard', () => {
  const originalRemoveChild = Node.prototype.removeChild;
  const originalInsertBefore = Node.prototype.insertBefore;

  beforeEach(() => {
    Node.prototype.removeChild = originalRemoveChild;
    Node.prototype.insertBefore = originalInsertBefore;
    delete Node.prototype.__brikopsDomGuard;
  });

  afterAll(() => {
    Node.prototype.removeChild = originalRemoveChild;
    Node.prototype.insertBefore = originalInsertBefore;
    delete Node.prototype.__brikopsDomGuard;
  });

  test('tolerates removing a node that belongs to another parent', () => {
    installDomGuard();
    const parent = document.createElement('div');
    const otherParent = document.createElement('div');
    const child = document.createElement('span');
    otherParent.appendChild(child);

    expect(parent.removeChild(child)).toBe(child);
    expect(child.parentNode).toBe(otherParent);
  });

  test('tolerates inserting before a reference in another parent', () => {
    installDomGuard();
    const parent = document.createElement('div');
    const otherParent = document.createElement('div');
    const reference = document.createElement('span');
    const node = document.createElement('strong');
    otherParent.appendChild(reference);

    expect(parent.insertBefore(node, reference)).toBe(node);
    expect(node.parentNode).toBeNull();
  });

  test('preserves normal remove and insert behavior', () => {
    installDomGuard();
    const parent = document.createElement('div');
    const reference = document.createElement('span');
    const node = document.createElement('strong');
    parent.appendChild(reference);

    expect(parent.insertBefore(node, reference)).toBe(node);
    expect(parent.firstChild).toBe(node);
    expect(parent.removeChild(node)).toBe(node);
    expect(node.parentNode).toBeNull();
  });

  test('installs only once', () => {
    installDomGuard();
    const guardedRemoveChild = Node.prototype.removeChild;
    const guardedInsertBefore = Node.prototype.insertBefore;

    installDomGuard();

    expect(Node.prototype.removeChild).toBe(guardedRemoveChild);
    expect(Node.prototype.insertBefore).toBe(guardedInsertBefore);
  });
});