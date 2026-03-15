<?php
require_once 'includes/functions.php';
$pageTitle = 'Contacts';

global $CARRIER_GATEWAYS;
$alert = '';

// Handle actions
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';

    if ($action === 'add') {
        addContact($_POST['name'], $_POST['phone'], $_POST['carrier']);
        $alert = '<div class="alert alert-success">Contact added.</div>';
    } elseif ($action === 'edit') {
        updateContact((int)$_POST['id'], $_POST['name'], $_POST['phone'], $_POST['carrier']);
        $alert = '<div class="alert alert-success">Contact updated.</div>';
    } elseif ($action === 'delete') {
        deleteContact((int)$_POST['id']);
        $alert = '<div class="alert alert-success">Contact deleted.</div>';
    }
}

$contacts = getContacts();
$editContact = null;
if (isset($_GET['edit'])) {
    $editContact = getContact((int)$_GET['edit']);
}

include 'includes/header.php';
?>

<h1>Contacts</h1>
<?php echo $alert; ?>

<div class="card">
    <form method="post">
        <input type="hidden" name="action" value="<?php echo $editContact ? 'edit' : 'add'; ?>">
        <?php if ($editContact): ?>
            <input type="hidden" name="id" value="<?php echo $editContact['id']; ?>">
        <?php endif; ?>

        <div class="form-grid">
            <div class="form-row">
                <label for="name">Name</label>
                <input type="text" name="name" id="name" required value="<?php echo $editContact ? htmlspecialchars($editContact['name']) : ''; ?>" placeholder="John Doe">
            </div>
            <div class="form-row">
                <label for="phone">Phone</label>
                <input type="tel" name="phone" id="phone" required value="<?php echo $editContact ? htmlspecialchars($editContact['phone']) : ''; ?>" placeholder="5551234567">
            </div>
        </div>
        <div class="form-row">
            <label for="carrier">Carrier</label>
            <select name="carrier" id="carrier" required>
                <option value="">Select carrier...</option>
                <?php foreach ($CARRIER_GATEWAYS as $key => $info): ?>
                    <option value="<?php echo $key; ?>" <?php echo ($editContact && $editContact['carrier'] === $key) ? 'selected' : ''; ?>><?php echo htmlspecialchars($info['name']); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="btn-group">
            <button type="submit" class="btn btn-primary"><?php echo $editContact ? 'Update' : 'Add'; ?> Contact</button>
            <?php if ($editContact): ?>
                <a href="contacts.php" class="btn btn-outline">Cancel</a>
            <?php endif; ?>
        </div>
    </form>
</div>

<?php if ($contacts): ?>
<div class="card">
    <table>
        <thead>
            <tr><th>Name</th><th>Phone</th><th>Carrier</th><th>Actions</th></tr>
        </thead>
        <tbody>
        <?php foreach ($contacts as $c): ?>
            <tr>
                <td><?php echo htmlspecialchars($c['name']); ?></td>
                <td><?php echo htmlspecialchars($c['phone']); ?></td>
                <td><?php echo htmlspecialchars($CARRIER_GATEWAYS[$c['carrier']]['name'] ?? $c['carrier']); ?></td>
                <td>
                    <a href="contacts.php?edit=<?php echo $c['id']; ?>" class="btn btn-outline btn-sm">Edit</a>
                    <form method="post" style="display:inline" onsubmit="return confirm('Delete this contact?')">
                        <input type="hidden" name="action" value="delete">
                        <input type="hidden" name="id" value="<?php echo $c['id']; ?>">
                        <button type="submit" class="btn btn-danger btn-sm">Delete</button>
                    </form>
                </td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</div>
<?php else: ?>
<div class="empty">No contacts yet. Add one above.</div>
<?php endif; ?>

<?php include 'includes/footer.php'; ?>
