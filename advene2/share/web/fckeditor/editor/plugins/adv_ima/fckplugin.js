// Register the related commands.
var chemin = FCKPlugins.Items['adv_ima'].Path + 'adv_ima.html';
var chemin2 = 'packages/advene/view/adv_ima';
var chemin3 = 'packages/advene/view/_adv_ima';

FCKCommands.RegisterCommand( 'adv_ima', new FCKDialogCommand( FCKLang.AdvImaDlgTitle, FCKLang.AdvImaDlgTitle, chemin, 400, 300 ) ) ;
//

// Create the "AdvIMA" toolbar button.

var AdvIMAItem	= new FCKToolbarButton( 'adv_ima', FCKLang.AdvImaDlgTitle ) ;

AdvIMAItem.IconPath	= FCKConfig.PluginsPath + 'adv_ima/adv_ima.gif' ;



FCKToolbarItems.RegisterItem( 'adv_ima', AdvIMAItem ) ;


// clique droit menu deroulant ajouté item image
// pour ripristiner l'icone par defaut de FCK decommenter la partie commenté 
// dans 'fckeditor\editor\js\fckeditorcode_gecko.js' et dans
// 'fckeditor\editor\js\fckeditorcode_ie.js'
// a la ligne 106

var oMyContextMenuListener = new Object() ;

// This is the standard function called right before sowing the context menu.
oMyContextMenuListener.AddItems = function( contextMenu, tag, tagName )
{
	
  // Let's show our custom option only for images.
  if ( tagName == 'IMG')
	{
		contextMenu.AddSeparator() ;
		contextMenu.AddItem( 'adv_ima', FCKLang.AdvImaBtn, AdvIMAItem.IconPath ) ;
  }
}
FCK.ContextMenu.RegisterListener( oMyContextMenuListener ) ;

