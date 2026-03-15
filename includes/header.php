<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Text<?php echo isset($pageTitle) ? ' — ' . $pageTitle : ''; ?></title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<nav>
    <div class="nav-brand">Multi-Text</div>
    <div class="nav-links">
        <a href="index.php" class="<?php echo basename($_SERVER['PHP_SELF']) === 'index.php' ? 'active' : ''; ?>">Send</a>
        <a href="contacts.php" class="<?php echo basename($_SERVER['PHP_SELF']) === 'contacts.php' ? 'active' : ''; ?>">Contacts</a>
        <a href="groups.php" class="<?php echo basename($_SERVER['PHP_SELF']) === 'groups.php' ? 'active' : ''; ?>">Groups</a>
        <a href="history.php" class="<?php echo basename($_SERVER['PHP_SELF']) === 'history.php' ? 'active' : ''; ?>">History</a>
    </div>
</nav>
<main>
