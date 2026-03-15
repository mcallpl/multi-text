<?php
require_once 'includes/functions.php';
$pageTitle = 'History';

global $CARRIER_GATEWAYS;
$alert = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'clear') {
    clearHistory();
    $alert = '<div class="alert alert-success">History cleared.</div>';
}

$messages = getMessageHistory(100);

include 'includes/header.php';
?>

<h1>Message History</h1>
<?php echo $alert; ?>

<?php if ($messages): ?>
<div style="text-align:right;margin-bottom:1rem">
    <form method="post" style="display:inline" onsubmit="return confirm('Clear all message history?')">
        <input type="hidden" name="action" value="clear">
        <button type="submit" class="btn btn-danger btn-sm">Clear History</button>
    </form>
</div>

<div class="card">
    <table>
        <thead><tr><th>Date</th><th>To</th><th>Carrier</th><th>Message</th><th>Status</th></tr></thead>
        <tbody>
        <?php foreach ($messages as $m): ?>
            <tr>
                <td style="white-space:nowrap"><?php echo date('M j, g:ia', strtotime($m['sent_at'])); ?></td>
                <td><?php echo htmlspecialchars($m['contact_name'] ?: $m['phone']); ?></td>
                <td><?php echo htmlspecialchars($CARRIER_GATEWAYS[$m['carrier']]['name'] ?? $m['carrier']); ?></td>
                <td><?php echo htmlspecialchars(mb_strimwidth($m['message'], 0, 50, '...')); ?></td>
                <td><span class="badge badge-<?php echo $m['status']; ?>"><?php echo $m['status']; ?></span></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</div>
<?php else: ?>
<div class="empty">No messages sent yet.</div>
<?php endif; ?>

<?php include 'includes/footer.php'; ?>
