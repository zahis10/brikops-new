// Chrome/Google Translate rewrites text nodes by wrapping them in <font>
// elements. React can then hold stale parent references and throw NotFoundError
// on its next commit (facebook/react#11538). Tolerate those stale references so
// translated text may be stale, but the application does not crash.
export function installDomGuard() {
  if (typeof Node !== 'function' || !Node.prototype) return;
  if (Node.prototype.__brikopsDomGuard) return;

  const originalRemoveChild = Node.prototype.removeChild;
  Node.prototype.removeChild = function removeChild(child) {
    if (child && child.parentNode !== this) return child;
    return originalRemoveChild.apply(this, arguments);
  };

  const originalInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function insertBefore(newNode, referenceNode) {
    if (referenceNode && referenceNode.parentNode !== this) return newNode;
    return originalInsertBefore.apply(this, arguments);
  };

  Node.prototype.__brikopsDomGuard = true;
}