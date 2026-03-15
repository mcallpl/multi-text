<?php
require_once 'includes/functions.php';
$pageTitle = 'Groups';

$alert = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';

    if ($action === 'add_group') {
        addGroup($_POST['name']);
        $alert = '<div class="alert alert-success">Group created.</div>';
    } elseif ($action === 'delete_group') {
        deleteGroup((int)$_POST['id']);
        $alert = '<div class="alert alert-success">Group deleted.</div>';
    } elseif ($action === 'add_member') {
        addGroupMember((int)$_POST['group_id'], (int)$_POST['contact_id']);
        $alert = '<div class="alert alert-success">Member added.</div>';
    } elseif ($action === 'remove_member') {
        removeGroupMember((int)$_POST['group_id'], (int)$_POST['contact_id']);
        $alert = '<div class="alert alert-success">Member removed.</div>';
    }
}

$groups = getGroups();
$contacts = getContacts();
$viewGroup = null;
$groupMembers = [];

if (isset($_GET['view'])) {
    $viewGroup = getGroup((int)$_GET['view']);
    if ($viewGroup) {
        $groupMembers = getGroupMembers($viewGroup['id']);
    }
}

include 'includes/header.php';
?>

<h1>Groups</h1>
<?php echo $alert; ?>

<?php if (!$viewGroup): ?>

<div class="card">
    <form method="post">
        <input type="hidden" name="action" value="add_group">
        <div class="form-row">
            <label for="name">New Group Name</label>
            <input type="text" name="name" id="name" required placeholder="Family, Work, etc.">
        </div>
        <button type="submit" class="btn btn-primary">Create Group</button>
    </form>
</div>

<?php if ($groups): ?>
<div class="card">
    <table>
        <thead><tr><th>Group</th><th>Members</th><th>Actions</th></tr></thead>
        <tbody>
        <?php foreach ($groups as $g): ?>
            <tr>
                <td><?php echo htmlspecialchars($g['name']); ?></td>
                <td><?php echo $g['member_count']; ?></td>
                <td>
                    <a href="groups.php?view=<?php echo $g['id']; ?>" class="btn btn-outline btn-sm">Manage</a>
                    <form method="post" style="display:inline" onsubmit="return confirm('Delete this group?')">
                        <input type="hidden" name="action" value="delete_group">
                        <input type="hidden" name="id" value="<?php echo $g['id']; ?>">
                        <button type="submit" class="btn btn-danger btn-sm">Delete</button>
                    </form>
                </td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</div>
<?php else: ?>
<div class="empty">No groups yet. Create one above.</div>
<?php endif; ?>

<?php else: ?>

<a href="groups.php" class="btn btn-outline btn-sm" style="margin-bottom:1rem">&larr; Back to Groups</a>

<div class="card">
    <h1 style="margin-bottom:1rem"><?php echo htmlspecialchars($viewGroup['name']); ?></h1>

    <?php if ($contacts): ?>
    <form method="post" style="display:flex;gap:0.5rem;margin-bottom:1.5rem">
        <input type="hidden" name="action" value="add_member">
        <input type="hidden" name="group_id" value="<?php echo $viewGroup['id']; ?>">
        <select name="contact_id" required style="flex:1">
            <option value="">Add a contact...</option>
            <?php
            $memberIds = array_column($groupMembers, 'id');
            foreach ($contacts as $c):
                if (!in_array($c['id'], $memberIds)):
            ?>
                <option value="<?php echo $c['id']; ?>"><?php echo htmlspecialchars($c['name']); ?></option>
            <?php endif; endforeach; ?>
        </select>
        <button type="submit" class="btn btn-primary btn-sm">Add</button>
    </form>
    <?php endif; ?>

    <?php if ($groupMembers): ?>
    <table>
        <thead><tr><th>Name</th><th>Phone</th><th></th></tr></thead>
        <tbody>
        <?php foreach ($groupMembers as $m): ?>
            <tr>
                <td><?php echo htmlspecialchars($m['name']); ?></td>
                <td><?php echo htmlspecialchars($m['phone']); ?></td>
                <td>
                    <form method="post" style="display:inline">
                        <input type="hidden" name="action" value="remove_member">
                        <input type="hidden" name="group_id" value="<?php echo $viewGroup['id']; ?>">
                        <input type="hidden" name="contact_id" value="<?php echo $m['id']; ?>">
                        <button type="submit" class="btn btn-danger btn-sm">Remove</button>
                    </form>
                </td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    <?php else: ?>
    <div class="empty">No members in this group yet.</div>
    <?php endif; ?>
</div>

<?php endif; ?>

<?php include 'includes/footer.php'; ?>
