<?php
require_once 'includes/functions.php';
$pageTitle = 'Send Message';

$alert = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $message = trim($_POST['message'] ?? '');
    $sendTo = $_POST['send_to'] ?? '';

    if (empty($message)) {
        $alert = '<div class="alert alert-error">Message cannot be empty.</div>';
    } elseif (empty($sendTo)) {
        $alert = '<div class="alert alert-error">Select a recipient.</div>';
    } else {
        if (strpos($sendTo, 'group_') === 0) {
            $groupId = (int)str_replace('group_', '', $sendTo);
            $results = sendToGroup($groupId, $message);
            $total = count($results);
            $ok = count(array_filter($results, fn($r) => $r['success']));
            $alert = "<div class=\"alert alert-success\">Sent to {$ok}/{$total} contacts in group.</div>";
        } else {
            $contactId = (int)$sendTo;
            $contact = getContact($contactId);
            if ($contact) {
                $result = sendSMS($contact['phone'], $contact['carrier'], $message, $contact['id'], $contact['name']);
                $alert = $result['success']
                    ? '<div class="alert alert-success">Message sent to ' . htmlspecialchars($contact['name']) . '.</div>'
                    : '<div class="alert alert-error">Failed to send message.</div>';
            }
        }
    }
}

$contacts = getContacts();
$groups = getGroups();

include 'includes/header.php';
?>

<h1>Send Message</h1>
<?php echo $alert; ?>

<div class="card">
    <form method="post">
        <div class="form-row">
            <label for="send_to">To</label>
            <select name="send_to" id="send_to" required>
                <option value="">Select recipient...</option>
                <?php if ($contacts): ?>
                    <optgroup label="Contacts">
                    <?php foreach ($contacts as $c): ?>
                        <option value="<?php echo $c['id']; ?>"><?php echo htmlspecialchars($c['name']); ?> (<?php echo htmlspecialchars($c['phone']); ?>)</option>
                    <?php endforeach; ?>
                    </optgroup>
                <?php endif; ?>
                <?php if ($groups): ?>
                    <optgroup label="Groups">
                    <?php foreach ($groups as $g): ?>
                        <option value="group_<?php echo $g['id']; ?>"><?php echo htmlspecialchars($g['name']); ?> (<?php echo $g['member_count']; ?> members)</option>
                    <?php endforeach; ?>
                    </optgroup>
                <?php endif; ?>
            </select>
        </div>
        <div class="form-row">
            <label for="message">Message</label>
            <textarea name="message" id="message" maxlength="160" placeholder="Type your message..." required></textarea>
            <div class="char-count"><span id="charCount">0</span>/160</div>
        </div>
        <button type="submit" class="btn btn-primary">Send SMS</button>
    </form>
</div>

<script>
const ta = document.getElementById('message');
const cc = document.getElementById('charCount');
ta.addEventListener('input', () => {
    cc.textContent = ta.value.length;
    cc.parentElement.classList.toggle('over', ta.value.length > 160);
});
</script>

<?php include 'includes/footer.php'; ?>
