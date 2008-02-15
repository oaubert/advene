// Register the related commands.

FCKCommands.RegisterCommand( 'richedit_annotation', new FCKDialogCommand( FCKLang['DlgAdveneIMGTitle'], FCKLang['DlgAdveneIMGBtn'], '/packages/advene/view/_richedit_annotation', 700, 600 ) ) ;


// Create the "AdveneIMG" toolbar button.

var AdveneIMGItem	= new FCKToolbarButton( 'richedit_annotation', FCKLang['DlgAdveneIMGTitle'] ) ;

AdveneIMGItem.IconPath	= FCKConfig.PluginsPath + 'richedit_annotation/adv.gif' ;



FCKToolbarItems.RegisterItem( 'richedit_annotation', AdveneIMGItem ) ;


// clique droit menu deroulant a debugger class du tag 

var oMyContextMenuListener = new Object() ;

// This is the standard function called right before sowing the context menu.
oMyContextMenuListener.AddItems = function( contextMenu, tag, tagName )
{
	// Let's show our custom option only for images.
	/*if ( tagName == 'SPAN' && tag.className == 'AdveneContent'  )
	{*/
		contextMenu.AddSeparator() ;
		contextMenu.AddItem( 'richedit_annotation', FCKLang['DlgAdveneIMGTitle'], AdveneIMGItem.IconPath ) ;
	//}
}

FCK.ContextMenu.RegisterListener( oMyContextMenuListener ) ;
