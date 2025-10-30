export const getThemeHtmlStyles = (additionalClasses: string = ""): string => {
    return `
    whitespace-normal
	  break-words
    leading-[24px]
    
    /* Typography */
    [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-4 [&_h1]:mt-6 [&_h1]:text-foreground
    [&_h2]:text-xl [&_h2]:font-bold [&_h2]:mb-3 [&_h2]:mt-5 [&_h2]:text-foreground
    [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-foreground
    [&_h4]:text-base [&_h4]:font-semibold [&_h4]:mb-2 [&_h4]:mt-3 [&_h4]:text-foreground
    [&_h5]:text-sm [&_h5]:font-semibold [&_h5]:mb-1 [&_h5]:mt-2 [&_h5]:text-foreground
    [&_h6]:text-xs [&_h6]:font-semibold [&_h6]:mb-1 [&_h6]:mt-2 [&_h6]:text-foreground
    
    /* Paragraphs */
    [&_p]:mb-2 [&_p]:leading-[24px] [&_p]:text-foreground

    /* Text formatting */
    [&_strong]:font-semibold [&_strong]:text-foreground
    [&_em]:italic
    [&_del]:line-through [&_del]:text-foreground

    /* Links */
    [&_a]:text-[var(--color-primary-wMain)] [&_a]:underline [&_a]:decoration-[var(--color-primary-wMain)] dark:[&_a]:text-[var(--color-primary-w20)] dark:[&_a]:decoration-[var(--color-primary-w20)]
    [&_a:hover]:text-[var(--color-primary-w100)] [&_a:hover]:decoration-[var(--color-primary-w100)] dark:[&_a:hover]:text-[var(--color-primary-w10)] dark:[&_a:hover]:decoration-[var(--color-primary-w10)]

    /* Lists */
    [&_ul]:mb-4 [&_ul]:pl-6 [&_ul]:list-disc [&_ul]:space-y-1
    [&_ol]:mb-4 [&_ol]:pl-6 [&_ol]:list-decimal [&_ol]:space-y-1
    [&_li]:text-foreground [&_li]:leading-[24px]
    [&_ul_ul]:mt-1 [&_ul_ul]:mb-1
    [&_ol_ol]:mt-1 [&_ol_ol]:mb-1
    
    /* Code */
    [&_code]:bg-transparent [&_code]:py-0.5 [&_code]:rounded
    [&_code]:text-sm [&_code]:font-mono [&_code]:font-semibold [&_code]:text-foreground [&_code]:break-words
    [&_pre]:bg-transparent [&_pre]:p-4 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:max-w-full
    [&_pre]:mb-4 [&_pre]:border [&_pre]:border-border [&_pre]:whitespace-pre-wrap
    [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-sm [&_pre_code]:break-words
    
    /* Blockquotes */
    [&_blockquote]:border-l-4 [&_blockquote]:border-border [&_blockquote]:pl-4
    [&_blockquote]:py-2 [&_blockquote]:mb-4 [&_blockquote]:italic
    [&_blockquote]:text-foreground [&_blockquote]:bg-transparent
    
    /* Tables */
    [&_table]:w-full [&_table]:mb-4 [&_table]:border-collapse [&_table]:table-fixed [&_table]:max-w-full
    [&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-2 [&_th]:break-words
    [&_th]:bg-transparent [&_th]:font-semibold [&_th]:text-left
    [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2 [&_td]:break-words
    [&_tr:nth-child(even)]:bg-transparent
    
    /* Horizontal rules */
    [&_hr]:border-0 [&_hr]:border-t [&_hr]:border-border [&_hr]:my-6

    /* Images */
    [&_img]:max-w-full [&_img]:h-auto [&_img]:rounded [&_img]:my-2 [&_img]:object-contain

    ${additionalClasses}
  `
        .trim()
        .replace(/\s+/g, " ");
};

export const getThemeButtonHtmlStyles = (additionalClasses: string = ""): string => {
    return `
    /* Buttons - "important" overrides for flow controls */
    [&>button]:bg-[var(--color-background-w10)]
    [&>button]:dark:!bg-[var(--color-background-w100)]
    [&>button]:hover:bg-[var(--color-background-w20)]
    [&>button]:dark:hover:!bg-[var(--color-primary-w60)]
    [&>button]:text-[var(--color-primary-text-wMain)] 
    [&>button]:dark:text-[var(--color-primary-text-w10)]
    [&>button]:!border
    [&>button]:!border-[var(--color-secondary-w40)]
    [&>button]:dark:!border-[var(--color-secondary-w70)]

    ${additionalClasses}
  `
        .trim()
        .replace(/\s+/g, " ");
};
